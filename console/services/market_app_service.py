# -*- coding: utf8 -*-
"""
  Created on 18/3/5.
"""
import datetime
import json
import logging
import time

from console.constants import AppConstants
from console.enum.component_enum import ComponentType
from console.exception.bcode import ErrAppConfigGroupExists
from console.exception.main import (ErrVolumePath, MarketAppLost, RbdAppNotFound, ServiceHandleException)
from console.models.main import (RainbondCenterApp, RainbondCenterAppVersion, ServiceMonitor)
from console.repositories.app import (app_market_repo, app_tag_repo, service_source_repo)
from console.repositories.app_config import extend_repo, volume_repo
from console.repositories.base import BaseConnection
from console.repositories.group import tenant_service_group_repo
from console.repositories.market_app_repo import (app_import_record_repo, rainbond_app_repo)
from console.repositories.plugin import plugin_repo
from console.repositories.share_repo import share_repo
from console.repositories.team_repo import team_repo
from console.repositories.service_repo import service_repo
from console.services.app import app_market_service, app_service
from console.services.app_actions import app_manage_service
from console.services.app_config import (AppMntService, env_var_service, port_service, probe_service, volume_service)
from console.services.app_config.app_relation_service import \
    AppServiceRelationService
from console.services.app_config.component_graph import component_graph_service
from console.services.app_config.service_monitor import service_monitor_repo
from console.services.app_config_group import app_config_group_service
from console.services.group_service import group_service
from console.services.plugin import (app_plugin_service, plugin_config_service, plugin_service, plugin_version_service)
from console.services.upgrade_services import upgrade_service
from console.services.user_services import user_services
from console.utils import slug_util
from console.utils.version import compare_version
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from www.apiclient.regionapi import RegionInvokeApi
from www.models.main import (TenantEnterprise, TenantEnterpriseToken, TenantServiceInfo, Users)
from www.models.plugin import ServicePluginConfigVar
from www.tenantservice.baseservice import BaseTenantService
from www.utils.crypt import make_uuid

logger = logging.getLogger("default")
baseService = BaseTenantService()
app_relation_service = AppServiceRelationService()
region_api = RegionInvokeApi()
mnt_service = AppMntService()


class MarketAppService(object):
    def install_service(self,
                        tenant,
                        region,
                        user,
                        group_id,
                        market_app,
                        market_app_version,
                        is_deploy,
                        install_from_cloud,
                        market_name=None):
        service_list = []
        service_key_dep_key_map = {}
        key_service_map = {}
        tenant_service_group = None
        service_probe_map = {}
        app_plugin_map = {}  # 新装组件对应的安装的插件映射
        old_new_id_map = {}  # 新旧组件映射关系
        svc_key_id_map = {}  # service_key与组件映射关系
        try:
            app_templates = json.loads(market_app_version.app_template)
            apps = app_templates["apps"]
            tenant_service_group = self.__create_tenant_service_group(region, tenant.tenant_id, group_id, market_app.app_id,
                                                                      market_app_version.version, market_app.app_name)
            plugins = app_templates.get("plugins", [])
            if plugins:
                self.create_plugin_for_tenant(region, user, tenant, plugins)

            app_map = {}
            for app in apps:
                app_map[app.get("service_share_uuid")] = app
                app["update_time"] = market_app_version.update_time
                ts = self.__init_market_app(tenant, region, user, app, tenant_service_group.ID, install_from_cloud, market_name)
                # Record the application's installation source information
                service_source_data = {
                    "group_key":
                    market_app.app_id,
                    "version":
                    market_app_version.version,
                    "service_share_uuid":
                    app.get("service_share_uuid") if app.get("service_share_uuid", None) else app.get("service_key"),
                }
                service_source_repo.update_service_source(ts.tenant_id, ts.service_id, **service_source_data)
                group_service.add_service_to_group(tenant, region, group_id, ts.service_id)
                service_list.append(ts)
                old_new_id_map[app["service_id"]] = ts
                svc_key_id_map[app["service_key"]] = ts

                # 先保存env,再保存端口，因为端口需要处理env
                code, msg = self.__save_env(tenant, ts, app["service_env_map_list"], app["service_connect_info_map_list"])
                if code != 200:
                    raise Exception(msg)
                code, msg = self.__save_port(tenant, ts, app["port_map_list"])
                if code != 200:
                    raise Exception(msg)
                self.__save_volume(tenant, ts, app["service_volume_map_list"])

                # 保存组件探针信息
                probe_infos = app.get("probes", None)
                if probe_infos:
                    service_probe_map[ts.service_id] = probe_infos

                self.__save_extend_info(ts, app["extend_method_map"])
                if app.get("service_share_uuid", None):
                    dep_apps_key = app.get("dep_service_map_list", None)
                    if dep_apps_key:
                        service_key_dep_key_map[app.get("service_share_uuid")] = dep_apps_key
                    key_service_map[app.get("service_share_uuid")] = ts
                else:
                    dep_apps_key = app.get("dep_service_map_list", None)
                    if dep_apps_key:
                        service_key_dep_key_map[ts.service_key] = dep_apps_key
                    key_service_map[ts.service_key] = ts
                app_plugin_map[ts.service_id] = app.get("service_related_plugin_config")

                # component graphs
                component_graphs = app.get("component_graphs", {})
                component_graph_service.bulk_create(ts.service_id, component_graphs)

            # 保存依赖关系
            self.__save_service_deps(tenant, service_key_dep_key_map, key_service_map)

            # 数据中心创建组件
            new_service_list = self.__create_region_services(tenant, region, user, service_list, service_probe_map)

            # config groups
            config_groups = app_templates["app_config_groups"] if app_templates.get("app_config_groups") else []
            for config_group in config_groups:
                component_ids = []
                for service_key in config_group.get("component_keys", []):
                    if not svc_key_id_map.get(service_key):
                        continue
                    component_ids.append(svc_key_id_map.get(service_key).service_id)
                config_items = config_group.get("config_items", {})
                items = [{"item_key": key, "item_value": config_items[key]} for key in config_items]
                try:
                    app_config_group_service.create_config_group(group_id, config_group["name"], items,
                                                                 config_group["injection_type"], True, component_ids, region,
                                                                 tenant.tenant_name)
                except ErrAppConfigGroupExists:
                    app_config_group_service.create_config_group(group_id, config_group["name"] + "-" + make_uuid()[:4], items,
                                                                 config_group["injection_type"], True, component_ids, region,
                                                                 tenant.tenant_name)

            # 创建组件插件
            self.__create_service_plugins(region, tenant, service_list, app_plugin_map, old_new_id_map)

            # dependent volume
            self.__create_dep_mnt(tenant, apps, app_map, key_service_map)

            # component monitors
            component_monitors = app.get("component_monitors", {})
            self.__create_component_monitor(tenant, new_service_list, component_monitors)

            events = []
            if is_deploy:
                # 部署所有组件
                events = self.__deploy_services(tenant, user, new_service_list)
            return tenant_service_group, events
        except Exception as e:
            logger.exception(e)
            if tenant_service_group:
                tenant_service_group_repo.delete_tenant_service_group_by_pk(tenant_service_group.ID)
            for service in service_list:
                try:
                    app_manage_service.truncate_service(tenant, service)
                except Exception as le:
                    logger.exception(le)
            raise ServiceHandleException(msg="install app failure", msg_show="安装组件发生异常")

    def install_service_when_upgrade_app(self,
                                         tenant,
                                         region,
                                         user,
                                         group_id,
                                         market_app,
                                         old_app,
                                         services,
                                         is_deploy,
                                         install_from_cloud=False,
                                         market_name=None):
        service_list = []
        service_key_dep_key_map = {}
        key_service_map = {}
        tenant_service_group = None
        service_probe_map = {}
        app_plugin_map = {}  # 新装组件对应的安装的插件映射
        old_new_id_map = {}  # 新旧组件映射关系
        svc_key_id_map = {}  # service_key与组件映射关系

        for service in services:
            service_share_uuid = service.service_source_info.service_share_uuid
            if service_share_uuid:
                key_service_map[service_share_uuid] = service
            else:
                key_service_map[service.service_key] = service

        app_map = {app.get('service_share_uuid'): app for app in json.loads(old_app.template)["apps"]}

        try:
            app_templates = json.loads(market_app.template)
            apps = app_templates["apps"]
            tenant_service_group = self.__create_tenant_service_group(region, tenant.tenant_id, group_id, market_app.app_id,
                                                                      market_app.version, market_app.app_name)

            self.create_plugin_for_tenant(region, user, tenant, app_templates.get("plugins", []))

            for app in apps:
                app["update_time"] = market_app.update_time
                ts = self.__init_market_app(
                    tenant,
                    region,
                    user,
                    app,
                    tenant_service_group.ID,
                    install_from_cloud=install_from_cloud,
                    market_name=market_name)
                service_source_data = {
                    "group_key":
                    market_app.app_id,
                    "version":
                    market_app.version,
                    "service_share_uuid":
                    app.get("service_share_uuid") if app.get("service_share_uuid", None) else app.get("service_key")
                }
                service_source_repo.update_service_source(ts.tenant_id, ts.service_id, **service_source_data)
                group_service.add_service_to_group(tenant, region, group_id, ts.service_id)
                service_list.append(ts)
                old_new_id_map[app["service_id"]] = ts
                svc_key_id_map[app["service_key"]] = ts

                # 先保存env,再保存端口，因为端口需要处理env
                code, msg = self.__save_env(tenant, ts, app["service_env_map_list"], app["service_connect_info_map_list"])
                if code != 200:
                    raise Exception(msg)
                code, msg = self.__save_port(tenant, ts, app["port_map_list"])
                if code != 200:
                    raise Exception(msg)
                self.__save_volume(tenant, ts, app["service_volume_map_list"])

                # 保存组件探针信息
                probe_infos = app.get("probes", None)
                if probe_infos:
                    service_probe_map[ts.service_id] = probe_infos

                self.__save_extend_info(ts, app["extend_method_map"])
                if app.get("service_share_uuid", None):
                    dep_apps_key = app.get("dep_service_map_list", None)
                    if dep_apps_key:
                        service_key_dep_key_map[app.get("service_share_uuid")] = dep_apps_key
                    key_service_map[app.get("service_share_uuid")] = ts
                else:
                    dep_apps_key = app.get("dep_service_map_list", None)
                    if dep_apps_key:
                        service_key_dep_key_map[ts.service_key] = dep_apps_key
                    key_service_map[ts.service_key] = ts
                app_plugin_map[ts.service_id] = app.get("service_related_plugin_config")

                # component graphs
                component_graphs = app.get("component_graphs", {})
                component_graph_service.bulk_create(ts.service_id, component_graphs)

            # 数据中心创建组件
            new_service_list = self.__create_region_services(tenant, region, user, service_list, service_probe_map)

            # config groups
            config_groups = app_templates["app_config_groups"] if app_templates.get("app_config_groups") else []
            for config_group in config_groups:
                component_ids = []
                for service_key in config_group.get("component_keys", []):
                    if not svc_key_id_map.get(service_key):
                        continue
                    component_ids.append(svc_key_id_map.get(service_key).service_id)
                config_items = config_group.get("config_items", {})
                items = [{"item_key": key, "item_value": config_items[key]} for key in config_items]
                try:
                    app_config_group_service.create_config_group(group_id, config_group["name"], items,
                                                                 config_group["injection_type"], True, component_ids, region,
                                                                 tenant.tenant_name)
                except ErrAppConfigGroupExists:
                    old_cgroup = app_config_group_service.get_config_group(region, group_id, config_group["name"])
                    old_cgroup_service_ids = [
                        old_service["service_id"] for old_service in old_cgroup["services"]
                        if old_service["service_id"] not in component_ids
                    ]
                    old_cgroup_items = [{
                        "item_key": old_item["item_key"],
                        "item_value": old_item["item_value"]
                    } for old_item in old_cgroup["config_items"] if not config_items.get(old_item["item_key"])]

                    component_ids.extend(old_cgroup_service_ids)
                    items.extend(old_cgroup_items)

                    app_config_group_service.update_config_group(region, group_id, config_group["name"], items, True,
                                                                 component_ids, tenant.tenant_name)

            # open plugin for component
            for app in apps:
                service = old_new_id_map[app["service_id"]]
                plugin_component_configs = app_plugin_map[service.service_id]
                self.__create_service_pluginsv2(tenant, region, service, market_app.version, apps, plugin_component_configs)

            # component monitors
            component_monitors = app.get("component_monitors", {})
            self.__create_component_monitor(tenant, new_service_list, component_monitors)

            events = {}
            if is_deploy:
                # 部署所有组件
                events = self.__deploy_services(tenant, user, new_service_list)
            return {
                "tenant_service_group": tenant_service_group,
                "events": events,
                "service_key_dep_key_map": service_key_dep_key_map,
                "key_service_map": key_service_map,
                "apps": apps,
                "app_map": app_map,
            }
        except Exception as e:
            logger.exception(e)
            if tenant_service_group:
                tenant_service_group_repo.delete_tenant_service_group_by_pk(tenant_service_group.ID)
            for service in service_list:
                try:
                    app_manage_service.truncate_service(tenant, service)
                except Exception as le:
                    logger.exception(le)
            raise e

    def save_service_deps_when_upgrade_app(self, tenant, service_key_dep_key_map, key_service_map, apps, app_map):
        # 保存依赖关系
        self.__save_service_deps(tenant, service_key_dep_key_map, key_service_map)
        # dependent volume
        self.__create_dep_mnt(tenant, apps, app_map, key_service_map)

    def save_app_config_groups_when_upgrade_app(self, region_name, tenant, app_id, upgrade_service_infos):
        if not upgrade_service_infos:
            return
        # 数据库中当前应用下的所有配置组
        old_app_config_groups = app_config_group_service.list(region_name, app_id)

        new_config_groups = {}  # 需要被新创建的应用配置组
        need_update_config_groups = {}  # 需要被更新的应用配置组
        for service_id in upgrade_service_infos:
            if not upgrade_service_infos[service_id].get("app_config_groups"):
                continue
            for app_config_group in upgrade_service_infos[service_id]["app_config_groups"]["add"]:
                if not old_app_config_groups.get(app_config_group["name"]):
                    # 如果应用配置组不在数据库中，但是已存在于待创建配置组中，则只追加生效组件ID
                    if new_config_groups.get(app_config_group["name"]):
                        new_config_groups[app_config_group["name"]]["component_ids"].append(service_id)
                        continue
                    # 如果应用配置组不在数据库也不在待创建的配置组中，则将其加入待创建配置组
                    new_config_groups.update({app_config_group["name"]: app_config_group})
                    continue
                need_update_config_groups.update({app_config_group["name"]: app_config_group})

        # 创建新的应用配置组
        if new_config_groups:
            for new_cgroup_name in new_config_groups:
                config_items = new_config_groups[new_cgroup_name]["config_items"]
                items = [{"item_key": key, "item_value": config_items[key]} for key in config_items]
                app_config_group_service.create_config_group(
                    app_id, new_cgroup_name, items, new_config_groups[new_cgroup_name]["injection_type"], True,
                    new_config_groups[new_cgroup_name]["component_ids"], region_name, tenant.tenant_name)
        # 更新已有应用配置组
        if need_update_config_groups:
            for update_cgroup_name in need_update_config_groups:
                config_items = need_update_config_groups[update_cgroup_name]["config_items"]
                new_service_ids = need_update_config_groups[update_cgroup_name]["component_ids"]
                # 获取原有配置组的配置项和生效组件
                old_cgroup = app_config_group_service.get_config_group(region_name, app_id, update_cgroup_name)
                old_cgroup_service_ids = [
                    old_service["service_id"] for old_service in old_cgroup["services"]
                    if old_service["service_id"] not in new_service_ids
                ]
                old_cgroup_items = [{
                    "item_key": old_item["item_key"],
                    "item_value": old_item["item_value"]
                } for old_item in old_cgroup["config_items"] if not config_items.get(old_item["item_key"])]

                # 将需要升级的生效组件ID与原有配置组生效组件ID连接起来，构成更新配置组需要的组件ID列表
                new_service_ids.extend(old_cgroup_service_ids)
                # 将需要升级的配置项与原有配置组配置项连接起来，构成更新配置组需要的配置项列表
                new_items = [{"item_key": key, "item_value": config_items[key]} for key in config_items]
                new_items.extend(old_cgroup_items)
                app_config_group_service.update_config_group(region_name, app_id, update_cgroup_name, new_items, True,
                                                             new_service_ids, tenant.tenant_name)

    def __create_component_monitor(self, tenant, service_list, component_monitors):
        if not service_list:
            return
        for service in service_list:
            self.__save_monitors(tenant, service, component_monitors)

    def __create_dep_mnt(self, tenant, apps, app_map, key_service_map):
        for app in apps:
            # dependent volume
            dep_mnts = app.get("mnt_relation_list", None)
            service = key_service_map.get(app.get("service_share_uuid"))
            if dep_mnts:
                for item in dep_mnts:
                    dep_service = key_service_map.get(item["service_share_uuid"])
                    if not dep_service:
                        logger.info("Service share uuid: {}; dependent service not found".format(item["service_share_uuid"]))
                        continue
                    dep_app = app_map.get(item["service_share_uuid"])
                    if not dep_app:
                        logger.debug("Service share uuid: {}; ; app not found".format(item["service_share_uuid"]))
                        continue
                    volume_list = dep_app.get("service_volume_map_list")
                    if volume_list:
                        for volume in volume_list:
                            if volume["volume_name"] == item["mnt_name"]:
                                dep_volume = volume_repo.get_by_sid_name(dep_service.service_id, item["mnt_name"])
                                if dep_volume:
                                    mnt_service.add_service_mnt_relation(tenant, service, item["mnt_dir"], dep_volume)

    def __create_service_plugins(self, region, tenant, service_list, app_plugin_map, old_new_id_map):
        try:
            plugin_version_service.update_plugin_build_status(region, tenant)

            for service in service_list:
                plugins = app_plugin_map.get(service.service_id)
                if plugins:
                    for plugin_config in plugins:
                        plugin_key = plugin_config["plugin_key"]
                        p = plugin_repo.get_plugin_by_origin_share_id(tenant.tenant_id, plugin_key)
                        plugin_id = p[0].plugin_id
                        service_plugin_config_vars = plugin_config["attr"]
                        plugin_version = plugin_version_service.get_newest_plugin_version(tenant.tenant_id, plugin_id)
                        build_version = plugin_version.build_version

                        self.__save_service_config_values(service, plugin_id, build_version, service_plugin_config_vars,
                                                          old_new_id_map)

                        # 2.从console数据库取数据生成region数据
                        region_config = app_plugin_service.get_region_config_from_db(service, plugin_id, build_version)

                        data = dict()
                        data["plugin_id"] = plugin_id
                        data["switch"] = True
                        data["version_id"] = build_version
                        data.update(region_config)
                        app_plugin_service.create_service_plugin_relation(tenant.tenant_id, service.service_id, plugin_id,
                                                                          build_version)

                        region_api.install_service_plugin(service.service_region, tenant.tenant_name, service.service_alias,
                                                          data)

        except Exception as e:
            logger.exception(e)

    def __create_service_pluginsv2(self, tenant, region_name, service, version, components, plugins):
        try:
            app_plugin_service.create_plugin_4marketsvc(region_name, tenant, service, version, components, plugins)
        except ServiceHandleException as e:
            logger.warning("plugin data: {}; failed to create plugin: {}", plugins, e)

    def __save_service_config_values(self, service, plugin_id, build_version, service_plugin_config_vars, old_new_id_map):
        config_list = []

        for config in service_plugin_config_vars:
            dest_service_id, dest_service_alias = "", ""
            if config["service_meta_type"] == "downstream_port":
                ts = old_new_id_map[config["dest_service_id"]]
                if ts:
                    dest_service_id, dest_service_alias = ts.service_id, ts.service_alias
            config_list.append(
                ServicePluginConfigVar(
                    service_id=service.service_id,
                    plugin_id=plugin_id,
                    build_version=build_version,
                    service_meta_type=config["service_meta_type"],
                    injection=config["injection"],
                    dest_service_id=dest_service_id,
                    dest_service_alias=dest_service_alias,
                    container_port=config["container_port"],
                    attrs=config["attrs"],
                    protocol=config["protocol"]))
        ServicePluginConfigVar.objects.bulk_create(config_list)

    def create_plugin_for_tenant(self, region_name, user, tenant, plugins):
        for plugin in plugins:
            # 对需要安装的插件查看本地是否有安装
            tenant_plugin = plugin_repo.get_plugin_by_origin_share_id(tenant.tenant_id, plugin["plugin_key"])
            # 如果本地没有安装，进行安装操作
            if not tenant_plugin:
                try:
                    logger.info("start install plugin {} for tenant {}".format(plugin["plugin_key"], tenant.tenant_id))
                    status, msg = self.__install_plugin(region_name, user, tenant, plugin)
                    if status != 200:
                        raise ServiceHandleException(
                            msg="install plugin failure {}".format(msg), msg_show="创建插件失败", status_code=status)
                except Exception as e:
                    logger.exception(e)
                    raise ServiceHandleException(msg="install plugin failure", msg_show="创建插件失败", status_code=500)
            else:
                logger.debug("plugin {} is exist in tenant {}".format(plugin["plugin_key"], tenant.tenant_id))

    def __install_plugin(self, region_name, user, tenant, plugin_template):
        image = None
        image_tag = None
        if plugin_template["share_image"]:
            image_and_tag = plugin_template["share_image"].rsplit(":", 1)
            if len(image_and_tag) > 1:
                image = image_and_tag[0]
                image_tag = image_and_tag[1]
            else:
                image = image_and_tag[0]
                image_tag = "latest"

        plugin_params = {
            "tenant_id": tenant.tenant_id,
            "region": region_name,
            "create_user": user.user_id,
            "desc": plugin_template["desc"],
            "plugin_alias": plugin_template["plugin_alias"],
            "category": plugin_template["category"],
            "build_source": "image",
            "image": image,
            "code_repo": plugin_template["code_repo"],
            "username": plugin_template["plugin_image"]["hub_user"],
            "password": plugin_template["plugin_image"]["hub_password"]
        }
        status, msg, plugin_base_info = plugin_service.create_tenant_plugin(plugin_params)
        if status != 200:
            return status, msg

        plugin_base_info.origin = 'local_market'
        plugin_base_info.origin_share_id = plugin_template.get("plugin_key")
        plugin_base_info.save()

        build_version = plugin_template.get('build_version')
        min_memory = plugin_template.get('min_memory', 128)

        plugin_build_version = plugin_version_service.create_build_version(
            region_name,
            plugin_base_info.plugin_id,
            tenant.tenant_id,
            user.user_id,
            "",
            "unbuild",
            min_memory,
            image_tag=image_tag,
            code_version="",
            build_version=build_version)

        share_config_groups = plugin_template.get('config_groups', [])

        plugin_config_service.create_config_groups(plugin_base_info.plugin_id, build_version, share_config_groups)

        event_id = make_uuid()
        plugin_build_version.event_id = event_id
        plugin_build_version.plugin_version_status = "fixed"

        plugin_service.create_region_plugin(region_name, tenant, plugin_base_info, image_tag=image_tag)

        ret = plugin_service.build_plugin(region_name, plugin_base_info, plugin_build_version, user, tenant, event_id,
                                          plugin_template.get("plugin_image", None))
        plugin_build_version.build_status = ret.get('bean').get('status')
        plugin_build_version.save()
        return 200, "success"

    def __create_tenant_service_group(self, region, tenant_id, group_id, app_key, app_version, app_name):
        group_name = self.__generator_group_name("gr")
        params = {
            "tenant_id": tenant_id,
            "group_name": group_name,
            "group_alias": app_name,
            "group_key": app_key,
            "group_version": app_version,
            "region_name": region,
            "service_group_id": 0 if group_id == -1 else group_id
        }
        return tenant_service_group_repo.create_tenant_service_group(**params)

    def __generator_group_name(self, group_name):
        return '_'.join([group_name, make_uuid()[-4:]])

    def __create_region_services(self, tenant, region_name, user, service_list, service_probe_map):
        service_prob_id_map = {}
        new_service_list = []
        try:
            for service in service_list:
                # 数据中心创建组件
                new_service = app_service.create_region_service(tenant, service, user.nick_name)
                # 为组件添加探针
                probe_data = service_probe_map.get(service.service_id)
                probe_ids = []
                if probe_data:
                    for data in probe_data:
                        code, msg, probe = probe_service.add_service_probe(tenant, service, data)
                        if code == 200:
                            probe_ids.append(probe.probe_id)
                else:
                    code, msg, probe = app_service.add_service_default_porbe(tenant, service)
                    if probe:
                        probe_ids.append(probe.probe_id)
                if probe_ids:
                    service_prob_id_map[service.service_id] = probe_ids

                new_service_list.append(new_service)
            return new_service_list
        except Exception as e:
            logger.exception("local market install app error {0}".format(e))
            if service_list:
                for service in service_list:
                    if service_prob_id_map:
                        probe_ids = service_prob_id_map.get(service.service_id)
                        if probe_ids:
                            for probe_id in probe_ids:
                                try:
                                    probe_service.delete_service_probe(tenant, service, probe_id)
                                except Exception as le:
                                    logger.exception("local market install app delete service probe {0}".format(le))
            raise e

    def __deploy_services(self, tenant, user, service_list):
        try:
            body = dict()
            code, data = app_manage_service.deploy_services_info(body, service_list, tenant, user, oauth_instance=None)
            if code == 200:
                # 获取数据中心信息
                one_service = service_list[0]
                region_name = one_service.service_region
                try:
                    _, body = region_api.batch_operation_service(region_name, tenant.tenant_name, data)
                    result = body["bean"]["batche_result"]
                    events = {item.event_id: item.service_id for item in result}
                    return events
                except region_api.CallApiError as e:
                    logger.debug(data)
                    logger.exception(e)
                    return {}
        except Exception as e:
            logger.exception("batch deploy service error {0}".format(e))
            return {}

    def __save_service_deps(self, tenant, service_key_dep_key_map, key_service_map):
        if service_key_dep_key_map:
            for service_key in list(service_key_dep_key_map.keys()):
                ts = key_service_map[service_key]
                dep_keys = service_key_dep_key_map[service_key]
                for dep_key in dep_keys:
                    if dep_key["dep_service_key"] in key_service_map:
                        dep_service = key_service_map[dep_key["dep_service_key"]]
                        code, msg, d = app_relation_service.add_service_dependency(tenant, ts, dep_service.service_id, True)
                        if code != 200:
                            logger.error("save component dependency relation error {0}".format(msg))

    def __save_env(self, tenant, service, inner_envs, outer_envs):
        if not inner_envs and not outer_envs:
            return 200, "success"
        for env in inner_envs:
            code, msg, env_data = env_var_service.add_service_env_var(tenant, service, 0, env["name"], env["attr_name"],
                                                                      env.get("attr_value"), env.get("is_change", True),
                                                                      "inner")
            if code != 200 and code != 412:
                logger.error("save market app env error {0}".format(msg))
                return code, msg
        for env in outer_envs:
            container_port = env.get("container_port", 0)
            if container_port == 0:
                if env.get("attr_value") == "**None**":
                    env["attr_value"] = make_uuid()[:8]
                code, msg, env_data = env_var_service.add_service_env_var(tenant, service, container_port, env["name"],
                                                                          env["attr_name"], env.get("attr_value"),
                                                                          env.get("is_change", True), "outer")
                if code != 200 and code != 412:
                    logger.error("save market app env error {0}".format(msg))
                    return code, msg
        return 200, "success"

    def __save_port(self, tenant, service, ports):
        if not ports:
            return 200, "success"
        for port in ports:
            code, msg, port_data = port_service.add_service_port(
                tenant,
                service,
                int(port["container_port"]),
                port["protocol"],
                port["port_alias"],
                port["is_inner_service"],
                port["is_outer_service"],
                k8s_service_name=port.get("k8s_service_name"))
            if code != 200:
                logger.error("save market app port error: {}".format(msg))
                return code, msg
        return 200, "success"

    def __save_volume(self, tenant, service, volumes):
        if not volumes:
            return 200, "success"
        for volume in volumes:
            try:
                if "file_content" in list(volume.keys()) and volume["file_content"] != "":
                    volume_service.add_service_volume(tenant, service, volume["volume_path"], volume["volume_type"],
                                                      volume["volume_name"], volume["file_content"])
                else:
                    settings = volume_service.get_best_suitable_volume_settings(tenant, service, volume["volume_type"],
                                                                                volume.get("access_mode"),
                                                                                volume.get("share_policy"),
                                                                                volume.get("backup_policy"), None,
                                                                                volume.get("volume_provider_name"))
                    if settings["changed"]:
                        logger.debug('volume type changed from {0} to {1}'.format(volume["volume_type"],
                                                                                  settings["volume_type"]))
                        volume["volume_type"] = settings["volume_type"]
                        if volume["volume_type"] == "share-file":
                            volume["volume_capacity"] = 0
                    else:
                        settings["volume_capacity"] = volume.get("volume_capacity", 0)
                    volume_service.add_service_volume(tenant, service, volume["volume_path"], volume["volume_type"],
                                                      volume["volume_name"], None, settings)
            except ErrVolumePath:
                logger.warning("Volume {0} Path {1} error".format(volume["volume_name"], volume["volume_path"]))

    def __save_extend_info(self, service, extend_info):
        if not extend_info:
            return 200, "success"
        if len(service.version) > 255:
            service.version = service.version[:255]
        params = {
            "service_key": service.service_key,
            "app_version": service.version,
            "min_node": extend_info["min_node"],
            "max_node": extend_info["max_node"],
            "step_node": extend_info["step_node"],
            "min_memory": extend_info["min_memory"],
            "max_memory": extend_info["max_memory"],
            "step_memory": extend_info["step_memory"],
            "is_restart": extend_info["is_restart"]
        }
        extend_repo.create_extend_method(**params)

    @staticmethod
    def __save_monitors(tenant, service, monitors):
        if not monitors:
            return

        for monitor in monitors:
            monitor_name = monitor.get("name")
            # make monitor name unique
            try:
                ServiceMonitor.objects.get(tenant_id=tenant.tenant_id, name=monitor_name)
                monitor_name += "-" + make_uuid()[0:4]
                service_monitor_repo.create_component_service_monitor(tenant, service, monitor_name, monitor.get("path"),
                                                                      monitor.get("port"), monitor.get("service_show_name"),
                                                                      monitor.get("interval"))
            except ServiceMonitor.DoesNotExist:
                pass
            except ServiceHandleException as e:
                logger.exception("create component monitor failed: {0}".format(e))
                continue

    def __init_market_app(self, tenant, region, user, app, tenant_service_group_id, install_from_cloud=False, market_name=None):
        """
        初始化应用市场创建的应用默认数据
        """
        # 判断分享类型是否为slug包
        share_type = app.get("share_type")
        if share_type:
            is_slug = bool(share_type == "slug")
        else:
            is_slug = bool(slug_util.is_slug(app["image"], app["language"]))

        tenant_service = TenantServiceInfo()
        tenant_service.tenant_id = tenant.tenant_id
        tenant_service.service_id = make_uuid()
        tenant_service.service_cname = app["service_cname"]
        tenant_service.service_alias = "gr" + tenant_service.service_id[-6:]
        tenant_service.creater = user.pk
        if is_slug:
            tenant_service.image = app["image"]
        else:
            tenant_service.image = app.get("share_image", app["image"])
        tenant_service.cmd = app.get("cmd", "")
        tenant_service.service_region = region
        tenant_service.service_key = app["service_key"]
        tenant_service.desc = "market app "
        tenant_service.category = "app_publish"
        tenant_service.setting = ""
        # handle service type
        extend_method = app["extend_method"]
        if extend_method:
            if extend_method == "state":
                tenant_service.extend_method = ComponentType.state_multiple.value
            elif extend_method == "stateless":
                tenant_service.extend_method = ComponentType.stateless_multiple.value
            else:
                tenant_service.extend_method = extend_method

        tenant_service.env = ","
        tenant_service.min_node = app["extend_method_map"]["min_node"]
        if app["extend_method_map"].get("init_memory"):
            tenant_service.min_memory = app["extend_method_map"].get("init_memory")
        elif app["extend_method_map"].get("min_memory"):
            tenant_service.min_memory = app["extend_method_map"].get("min_memory")
        else:
            tenant_service.min_memory = 512
        tenant_service.min_cpu = baseService.calculate_service_cpu(region, tenant_service.min_memory)
        tenant_service.inner_port = 0
        tenant_service.version = app["version"]
        # deprecated
        if is_slug:
            if app.get("service_slug", None):
                tenant_service.namespace = app["service_slug"]["namespace"]
        else:
            if app.get("service_image", None) and app["service_image"]["namespace"]:
                tenant_service.namespace = app["service_image"]["namespace"]
            else:
                tenant_service.namespace = "default"
        tenant_service.update_version = 1
        tenant_service.port_type = "multi_outer"
        tenant_service.create_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        tenant_service.deploy_version = app["deploy_version"]
        tenant_service.git_project_id = 0
        tenant_service.service_type = "application"
        tenant_service.total_memory = tenant_service.min_node * tenant_service.min_memory
        tenant_service.volume_mount_path = ""
        tenant_service.host_path = ""
        tenant_service.code_from = ""
        tenant_service.language = ""
        tenant_service.service_source = AppConstants.MARKET
        tenant_service.create_status = "creating"
        tenant_service.tenant_service_group_id = tenant_service_group_id
        self.__init_service_source(tenant_service, app, install_from_cloud, market_name)
        # 存储并返回
        tenant_service.save()
        return tenant_service

    def save_max_node_in_extend_method(self, service_key, app):
        extend_method_obj = share_repo.get_service_extend_method_by_key(service_key)
        if extend_method_obj:
            for ex_me in extend_method_obj:
                if app["extend_method_map"]["max_node"]:
                    ex_me.max_node = app["extend_method_map"]["max_node"]
                    ex_me.save()

    def __init_service_source(self, ts, app, install_from_cloud=False, market_name=None):
        slug = app.get("service_slug", None)
        extend_info = {}
        if slug:
            extend_info = slug
            extend_info["slug_path"] = app.get("share_slug_path", "")
        else:
            extend_info = app.get("service_image")
        extend_info["source_deploy_version"] = app.get("deploy_version")
        extend_info["source_service_share_uuid"] = app.get("service_share_uuid") if app.get(
            "service_share_uuid", None) else app.get("service_key", "")
        if "update_time" in app:
            if type(app["update_time"]) == datetime.datetime:
                extend_info["update_time"] = app["update_time"].strftime('%Y-%m-%d %H:%M:%S')
            elif type(app["update_time"]) == str:
                extend_info["update_time"] = app["update_time"]
        if install_from_cloud:
            extend_info["install_from_cloud"] = True
            extend_info["market"] = "default"
            extend_info["market_name"] = market_name
        service_source_params = {
            "team_id": ts.tenant_id,
            "service_id": ts.service_id,
            "user_name": "",
            "password": "",
            "extend_info": json.dumps(extend_info)
        }
        service_source_repo.create_service_source(**service_source_params)

    def get_visiable_apps(self, user, eid, scope, app_name, tag_names=None, is_complete=True, page=1, page_size=10, need_install="false"):
        if scope == "team":
            # prepare teams
            is_admin = user_services.is_user_admin_in_current_enterprise(user, eid)
            if is_admin:
                teams = None
            else:
                teams = team_repo.get_tenants_by_user_id(user.user_id)
            if teams:
                teams = [team.tenant_name for team in teams]
            apps = rainbond_app_repo.get_rainbond_app_in_teams_by_querey(eid, scope, teams, app_name, tag_names, page,
                                                                         page_size, need_install)
            count = rainbond_app_repo.get_rainbond_app_total_count(eid, scope, teams, app_name, tag_names, need_install)
        else:
            # default scope is enterprise
            apps = rainbond_app_repo.get_rainbond_app_in_enterprise_by_query(eid, scope, app_name, tag_names, page, page_size, need_install)
            count = rainbond_app_repo.get_rainbond_app_total_count(eid, scope, None, app_name, tag_names, need_install)
        if not apps:
            return [], count[0].total

        self._patch_rainbond_app_tag(eid, apps)
        self._patch_rainbond_app_versions(eid, apps, is_complete)
        return apps, count[0].total

    # patch rainbond app tag
    def _patch_rainbond_app_tag(self, eid, apps):
        app_ids = [app.app_id for app in apps]
        tags = app_tag_repo.get_multi_apps_tags(eid, app_ids)
        if not tags:
            return
        app_with_tags = dict()
        for tag in tags:
            if not app_with_tags.get(tag.app_id):
                app_with_tags[tag.app_id] = []
            app_with_tags[tag.app_id].append({"tag_id": tag.ID, "name": tag.name})

        for app in apps:
            app.tags = app_with_tags.get(app.app_id)

    def _get_rainbond_app_min_memory(self, apps_model_versions):
        apps_min_memory = dict()
        for app_model_version in apps_model_versions:
            if not apps_min_memory.get(app_model_version.app_id):
                min_memory = 0
                try:
                    app_temp = json.loads(app_model_version.app_template)
                    for app in app_temp.get("apps"):
                        if app.get("extend_method_map"):
                            try:
                                if app.get("extend_method_map").get("init_memory"):
                                    min_memory += int(app.get("extend_method_map").get("init_memory"))
                                else:
                                    min_memory += int(app.get("extend_method_map").get("min_memory"))
                            except Exception:
                                pass
                    apps_min_memory[app_model_version.app_id] = min_memory
                except ValueError:
                    apps_min_memory[app_model_version.app_id] = min_memory
        return apps_min_memory

    # patch rainbond app versions
    def _patch_rainbond_app_versions(self, eid, apps, is_complete=None):
        app_ids = [app.app_id for app in apps]
        versions = rainbond_app_repo.get_rainbond_app_version_by_app_ids(eid, app_ids, is_complete)
        if not versions:
            return

        app_with_versions = dict()
        for version in versions:
            if not app_with_versions.get(version.app_id):
                app_with_versions[version.app_id] = []
            version_info = {
                "is_complete": version.is_complete,
                "version": version.version,
                "version_alias": version.version_alias,
                "dev_status": version.dev_status,
            }
            # If the versions are the same, take the last version information
            for info in app_with_versions[version.app_id]:
                if version_info["version"] in info["version"]:
                    info["is_complete"] = version_info["is_complete"]
                    info["version_alias"] = version_info["version_alias"]
                    info["dev_status"] = version_info["dev_status"]
            if version_info not in app_with_versions[version.app_id]:
                app_with_versions[version.app_id].append(version_info)

        apps_min_memory = self._get_rainbond_app_min_memory(versions)
        for app in apps:
            versions_info = app_with_versions.get(app.app_id)
            app.dev_status = ""
            if versions_info:
                # sort rainbond app versions by version
                versions_info = sorted(versions_info, key=lambda x: (x["dev_status"], x["version"]))
                # If there is a version to release, set the application to release state
                have_release = False
                for v in versions_info:
                    if "release" in v["dev_status"]:
                        have_release = True
                if have_release:
                    app.dev_status = "release"
            app.versions_info = versions_info
            app.min_memory = apps_min_memory.get(app.app_id, 0)

    def get_visiable_apps_v2(self, tenant, scope, app_name, dev_status, page, page_size):
        limit = ""
        where = 'WHERE A.is_complete=1 AND A.enterprise_id in ("public", "{}")'.format(tenant.enterprise_id)
        if scope:
            if scope == "team":
                where += ' AND A.share_team="{}"'.format(tenant.tenant_name)
            else:
                where += ' AND A.scope="{}"'.format(scope)
        else:
            where += ' AND ((A.share_team="{}") OR (A.scope in ("goodrain", "enterprise")))'.format(tenant.tenant_name)
        if app_name:
            where += ' AND A.group_name like "{}%"'.format(app_name)
        if dev_status:
            where += ' AND A.dev_status="{}"'.format(dev_status)
        if page is not None and page_size is not None:
            page = (page - 1) * page_size
            limit = "LIMIT {page}, {page_size}".format(page=page, page_size=page_size)
        sql = """
                SELECT
                    A.*,
                    CONCAT('[',
                        GROUP_CONCAT(
                        CONCAT('{"tag_id":"',C.ID,'"'),',',
                        CONCAT('"name":"',C.name),'"}')
                    ,']') as tags
                FROM rainbond_center_app A
                LEFT JOIN rainbond_center_app_tag_relation B
                ON A.group_key = B.group_key and A.enterprise_id = B.enterprise_id
                LEFT JOIN rainbond_center_app_tag C
                ON B.tag_id = C.ID
                """
        sql1 = """
                GROUP BY
                    A.group_key, A.version
                ORDER BY
                    A.create_time DESC
                """
        sql += where
        sql += sql1
        sql += limit
        conn = BaseConnection()
        result = conn.query(sql)
        return result

    def get_current_team_shared_apps(self, enterprise_id, current_team_name):
        return rainbond_app_repo.get_current_enter_visable_apps(enterprise_id).filter(share_team=current_team_name)

    def get_current_enterprise_shared_apps(self, enterprise_id):
        tenants = team_repo.get_teams_by_enterprise_id(enterprise_id)
        tenant_names = [t.tenant_name for t in tenants]
        # 获取企业分享的应用，并且排除返回在团队内的
        return rainbond_app_repo.get_current_enter_visable_apps(enterprise_id).filter(share_team__in=tenant_names).exclude(
            scope="team")

    def get_public_market_shared_apps(self, enterprise_id):
        return rainbond_app_repo.get_current_enter_visable_apps(enterprise_id).filter(scope="goodrain")

    def get_team_visiable_apps(self, tenant):
        tenants = team_repo.get_teams_by_enterprise_id(tenant.enterprise_id)
        tenant_names = [t.tenant_name for t in tenants]
        public_apps = Q(scope="goodrain")
        enterprise_apps = Q(share_team__in=tenant_names, scope="enterprise")
        team_apps = Q(share_team=tenant.tenant_name, scope="team")

        return rainbond_app_repo.get_current_enter_visable_apps(
            tenant.enterprise_id).filter(public_apps | enterprise_apps | team_apps)

    def get_rain_bond_app_by_pk(self, pk):
        app = rainbond_app_repo.get_rainbond_app_by_id(pk)
        if not app:
            return 404, None
        return 200, app

    def check_market_service_info(self, tenant, service):
        app_not_found = MarketAppLost("当前云市应用已删除")
        service_source = service_source_repo.get_service_source(tenant.tenant_id, service.service_id)
        if not service_source:
            logger.info("app has been delete on market:{0}".format(service.service_cname))
            raise app_not_found
        extend_info_str = service_source.extend_info
        extend_info = json.loads(extend_info_str)
        if not extend_info.get("install_from_cloud", False):
            rainbond_app, rainbond_app_version = market_app_service.get_rainbond_app_and_version(
                tenant.enterprise_id, service_source.group_key, service_source.version)
            if not rainbond_app or not rainbond_app_version:
                logger.info("app has been delete on market:{0}".format(service.service_cname))
                raise app_not_found
        else:
            # get from cloud
            try:
                market = app_market_service.get_app_market_by_name(
                    tenant.enterprise_id, extend_info.get("market_name"), raise_exception=True)
                resp = app_market_service.get_market_app_model_version(market, service_source.group_key, service_source.version)
                if not resp:
                    raise app_not_found
            except region_api.CallApiError as e:
                logger.exception("get market app failed: {0}".format(e))
                if e.status == 404:
                    raise app_not_found
                raise MarketAppLost("云市应用查询失败")

    def get_rainbond_app_and_version(self, enterprise_id, app_id, app_version):
        app, app_version = rainbond_app_repo.get_rainbond_app_and_version(enterprise_id, app_id, app_version)
        if not app:
            raise RbdAppNotFound("未找到该应用")
        return app, app_version

    def get_rainbond_app_version(self, eid, app_id, app_version):
        app_versions = rainbond_app_repo.get_rainbond_app_version_by_app_id_and_version(eid, app_id, app_version)
        if not app_versions:
            return None
        return app_versions

    def get_rainbond_app(self, eid, app_id):
        return rainbond_app_repo.get_rainbond_app_qs_by_key(eid, app_id)

    def update_rainbond_app_install_num(self, enterprise_id, app_id, app_version):
        rainbond_app_repo.add_rainbond_install_num(enterprise_id, app_id, app_version)

    def get_service_app_from_cloud(self, tenant, group_key, group_version, service_source):
        extent_info = json.loads(service_source.extend_info)
        market = app_market_service.get_app_market_by_name(
            tenant.enterprise_id, extent_info.get("market_name"), raise_exception=True)
        _, market_app_version = app_market_service.cloud_app_model_to_db_model(market, group_key, group_version)
        if market_app_version:
            apps_template = json.loads(market_app_version.app_template)
            apps = apps_template.get("apps")

            def func(x):
                result = x.get("service_share_uuid", None) == service_source.service_share_uuid \
                         or x.get("service_key", None) == service_source.service_share_uuid
                return result

            app = next(iter([x for x in apps if func(x)]), None)
        if app is None:
            fmt = "Group key: {0}; version: {1}; service_share_uuid: {2}; Rainbond app not found."
            raise RbdAppNotFound(fmt.format(service_source.group_key, group_version, service_source.service_share_uuid))
        return app

    def conversion_cloud_version_to_app(self, cloud_version):
        app = RainbondCenterApp(app_id=cloud_version.app_key_id, app_name="", source="cloud", scope="market")
        app_version = RainbondCenterAppVersion(
            app_id=cloud_version.app_key_id,
            version=cloud_version.app_version,
            share_user=0,
            record_id=0,
            source="cloud",
            scope="market",
            app_template=json.dumps(cloud_version.templete.to_dict()),
            is_complete=True,
            template_version=cloud_version.templete_version)
        return app, app_version

    def get_all_goodrain_market_apps(self, app_name, is_complete):
        if app_name:
            return rainbond_app_repo.get_all_rainbond_apps().filter(
                scope="goodrain", source="market", group_name__icontains=app_name)
        if is_complete:
            if is_complete == "true":
                return rainbond_app_repo.get_all_rainbond_apps().filter(scope="goodrain", source="market", is_complete=True)
            else:
                return rainbond_app_repo.get_all_rainbond_apps().filter(scope="goodrain", source="market", is_complete=False)
        return rainbond_app_repo.get_all_rainbond_apps().filter(scope="goodrain", source="market")

    def list_upgradeable_versions(self, tenant, service):
        component_source = service_source_repo.get_service_source(service.tenant_id, service.service_id)
        if component_source:
            market_name = component_source.get_market_name()
            market = None
            install_from_cloud = component_source.is_install_from_cloud()
            if install_from_cloud and market_name:
                market = app_market_repo.get_app_market_by_name(tenant.enterprise_id, market_name, raise_exception=True)
            return self.__get_upgradeable_versions(tenant.enterprise_id, component_source.group_key, component_source.version,
                                                   component_source.get_template_update_time(), install_from_cloud, market)
        return []

    def get_enterprise_access_token(self, enterprise_id, access_target):
        enter = TenantEnterprise.objects.get(enterprise_id=enterprise_id)
        try:
            return TenantEnterpriseToken.objects.get(enterprise_id=enter.pk, access_target=access_target)
        except TenantEnterpriseToken.DoesNotExist:
            return None

    def count_upgradeable_market_apps(self, tenant, region, app_id):
        service_sources = group_service.get_group_service_sources(app_id).filter(~Q(group_key=None))
        app_models = dict()
        for ss in service_sources:
            if (ss.group_key not in app_models) or compare_version(app_models[ss.group_key]['version'], ss.version) == -1:
                app_models[ss.group_key] = {'version': ss.version, 'component_source': ss}
        iterator = self.yield_app_info(app_models, tenant, app_id)
        market_apps = [market_app for market_app in iterator if len(market_app['upgrade_versions']) > 0]
        return len(market_apps)

    def get_market_apps_in_app(self, region, tenant, group):
        service_sources = group_service.get_group_service_sources(group.ID).filter(~Q(group_key=None))
        app_models = dict()
        for ss in service_sources:
            if (ss.group_key not in app_models) or compare_version(app_models[ss.group_key]['version'], ss.version) == -1:
                app_models[ss.group_key] = {'version': ss.version, 'component_source': ss}
        iterator = self.yield_app_info(app_models, tenant, group.ID)
        app_info_list = [app_info for app_info in iterator]
        return app_info_list

    def yield_app_info(self, app_models, tenant, app_id):
        for app_model_key in app_models:
            version = app_models[app_model_key]['version']
            component_source = app_models[app_model_key]['component_source']
            app_model = None
            market_name = component_source.get_market_name()
            market = None
            install_from_cloud = component_source.is_install_from_cloud()
            if install_from_cloud and market_name:
                market = app_market_repo.get_app_market_by_name(tenant.enterprise_id, market_name, raise_exception=True)
                if market:
                    app_model, _ = app_market_service.cloud_app_model_to_db_model(market, app_model_key, version=None)
            else:
                app_model, _ = rainbond_app_repo.get_rainbond_app_and_version(tenant.enterprise_id, app_model_key, version)
            if not app_model:
                continue
            dat = {
                'group_key': app_model_key,
                'group_name': app_model.app_name,
                'app_model_name': app_model.app_name,
                'app_model_id': app_model_key,
                'share_user': app_model.create_user,
                'share_team': app_model.create_team,
                'tenant_service_group_id': app_model.app_id,
                'pic': app_model.pic,
                'source': app_model.source,
                'market_name': market_name,
                'describe': app_model.describe,
                'enterprise_id': tenant.enterprise_id,
                'is_official': app_model.is_official,
                'details': app_model.details
            }
            not_upgrade_record = upgrade_service.get_app_not_upgrade_record(tenant.tenant_id, app_id, app_model_key)
            versions = self.__get_upgradeable_versions(tenant.enterprise_id, app_model_key, version,
                                                       component_source.get_template_update_time(), install_from_cloud, market)
            dat.update({
                'current_version': version,
                'can_upgrade': bool(versions),
                'upgrade_versions': (set(versions) if versions else []),
                'not_upgrade_record_id': not_upgrade_record.ID,
                'not_upgrade_record_status': not_upgrade_record.status,
            })
            yield dat

    def __get_upgradeable_versions(self,
                                   enterprise_id,
                                   app_model_key,
                                   current_version,
                                   current_version_time,
                                   install_from_cloud=False,
                                   market=None):
        # Simply determine if there is a version that can be upgraded, not attribute changes.
        versions = []
        app_version_list = []
        if install_from_cloud and market:
            app_version_list = app_market_service.get_market_app_model_versions(market, app_model_key)
        else:
            app_version_list = rainbond_app_repo.get_rainbond_app_versions(enterprise_id, app_model_key)
        if not app_version_list:
            return None
        for version in app_version_list:
            new_version_time = time.mktime(version.update_time.timetuple())
            # If the current version cannot be found, all versions are upgradable by default.
            if current_version:
                compare = compare_version(version.version, current_version)
                if compare == 1:
                    versions.append(version.version)
                elif current_version_time:
                    version_time = time.mktime(current_version_time.timetuple())
                    if compare == 0 and new_version_time > version_time:
                        versions.append(version.version)
            else:
                versions.append(version.version)
        versions = list(set(versions))
        versions.sort(reverse=True)
        return versions

    def get_current_version(self, enterprise_id, app_model_key, app_id):
        service_sources = group_service.get_group_service_sources(app_id).filter(Q(group_key=app_model_key))
        install_from_cloud = False
        market = None
        current_version = None
        if service_sources and len(service_sources) > 0:
            current_version = service_sources[0].version
            component_source = service_sources[0]
            for source in service_sources:
                if compare_version(source.version, current_version) == 1:
                    current_version = source.version
                    component_source = source
            market_name = component_source.get_market_name()
            install_from_cloud = component_source.is_install_from_cloud()
            if install_from_cloud and market_name:
                market = app_market_repo.get_app_market_by_name(enterprise_id, market_name, raise_exception=True)
        return current_version, component_source.get_template_update_time(), install_from_cloud, market

    def get_models_upgradeable_version(self, enterprise_id, app_model_key, app_id):
        current_version, current_version_update_time, install_from_cloud, market = self.get_current_version(
            enterprise_id, app_model_key, app_id)
        return self.__get_upgradeable_versions(enterprise_id, app_model_key, current_version, current_version_update_time,
                                               install_from_cloud, market)

    def delete_rainbond_app_all_info_by_id(self, enterprise_id, app_id):
        sid = transaction.savepoint()
        try:
            rainbond_app_repo.delete_app_tag_by_id(enterprise_id, app_id)
            rainbond_app_repo.delete_app_version_by_id(enterprise_id, app_id)
            rainbond_app_repo.delete_app_by_id(enterprise_id, app_id)
            transaction.savepoint_commit(sid)
        except Exception as e:
            logger.exception(e)
            if sid:
                transaction.savepoint_rollback(sid)

    @transaction.atomic
    def update_rainbond_app(self, enterprise_id, app_id, app_info):
        app = rainbond_app_repo.get_rainbond_app_by_app_id(enterprise_id, app_id)
        if not app:
            raise RbdAppNotFound(msg="app not found")
        app.app_name = app_info.get("name")
        app.describe = app_info.get("describe")
        app.pic = app_info.get("pic")
        app.details = app_info.get("details")
        app.dev_status = app_info.get("dev_status")
        app_tag_repo.create_app_tags_relation(app, app_info.get("tag_ids"))
        app.scope = app_info.get("scope")
        if app.scope == "team":
            # update create team
            create_team = app_info.get("create_team")
            if create_team:
                team = team_repo.get_team_by_team_name(create_team)
                if team:
                    app.create_team = create_team
        app.save()

    @transaction.atomic
    def create_rainbond_app(self, enterprise_id, app_info):
        app_id = make_uuid()
        app = RainbondCenterApp(
            app_id=app_id,
            app_name=app_info.get("app_name"),
            create_user=app_info.get("create_user"),
            create_team=app_info.get("create_team"),
            pic=app_info.get("pic"),
            source=app_info.get("source"),
            dev_status=app_info.get("dev_status"),
            scope=app_info.get("scope"),
            describe=app_info.get("describe"),
            enterprise_id=enterprise_id,
            details=app_info.get("details"),
        )
        app.save()
        # save app and tag relation
        if app_info.get("tag_ids"):
            app_tag_repo.create_app_tags_relation(app, app_info.get("tag_ids"))

    def update_rainbond_app_version_info(self, enterprise_id, app_id, version, **body):
        version = rainbond_app_repo.update_app_version(enterprise_id, app_id, version, **body)
        if not version:
            raise ServiceHandleException(msg="can't get version", msg_show="应用下无该版本", status_code=404)
        return version

    def delete_rainbond_app_version(self, enterprise_id, app_id, version):
        try:
            rainbond_app_repo.delete_app_version_by_version(enterprise_id, app_id, version)
        except Exception as e:
            logger.exception(e)
            raise e

    def get_rainbond_app_and_versions(self, enterprise_id, app_id, page, page_size):
        have_version = False
        app = rainbond_app_repo.get_rainbond_app_by_app_id(enterprise_id, app_id)
        app_versions = rainbond_app_repo.get_rainbond_app_versions_by_id(enterprise_id, app_id)
        if not app:
            raise RbdAppNotFound("未找到该应用")
        app_release = False
        if app_versions is not None:
            for version in app_versions:
                if version["version"]:
                    have_version = True
                version["release_user"] = ""
                version["share_user_id"] = version["share_user"]
                version["share_user"] = ""
                user = Users.objects.filter(user_id=version["release_user_id"]).first()
                share_user = Users.objects.filter(user_id=version["share_user_id"]).first()

                if user:
                    version["release_user"] = user.nick_name
                if share_user:
                    version["share_user"] = share_user.nick_name
                else:
                    record = app_import_record_repo.get_import_record(version["record_id"])
                    if record:
                        version["share_user"] = record.user_name
                version["dev_status"] = version.dev_status
                if version["dev_status"] == "release":
                    app_release = True

        tag_list = []
        tags = app_tag_repo.get_app_tags(enterprise_id, app_id)
        for t in tags:
            tag = app_tag_repo.get_tag_name(enterprise_id, t.tag_id)
            tag_list.append({"tag_id": t.tag_id, "name": tag.name})

        app = app.to_dict()
        app["tags"] = tag_list
        if app_release:
            app["dev_status"] = 'release'
        else:
            app["dev_status"] = ''
        p = Paginator(app_versions, page_size)
        total = p.count
        if have_version:
            return app, p.page(page).object_list, total
        return app, None, 0

    def list_rainbond_app_components(self, enterprise_id, tenant, app_id):
        """
        return the list of the rainbond app.
        """
        # list components by app_id
        component_sources = service_source_repo.list_by_app_id(tenant.tenant_id, app_id)
        if not component_sources:
            return None
        component_ids = [cs.service_id for cs in component_sources]
        components = service_repo.get_service_by_service_ids(component_ids)

        versions = self.list_app_versions(enterprise_id, component_sources[0])

        # make a map of component_sources
        component_sources = {cs.service_id: cs for cs in component_sources}

        result = []
        for component in components:
            component_source = component_sources[component.service_id]
            cpt = component.to_dict()
            cpt["upgradable_versions"] = self.__upgradable_versions(component_source, versions)
            result.append(cpt)

        return result

    @staticmethod
    def __upgradable_versions(component_source, versions):
        current_version = component_source.version
        current_version_time = component_source.get_template_update_time()
        result = []
        for version in versions:
            new_version_time = time.mktime(version.update_time.timetuple())
            compare = compare_version(version.version, current_version)
            if compare == 1:
                result.append(version.version)
            elif current_version_time:
                version_time = time.mktime(current_version_time.timetuple())
                if compare == 0 and new_version_time > version_time:
                    result.append(version.version)
        result = list(set(result))
        result.sort(reverse=True)
        return result

    @staticmethod
    def list_app_versions(enterprise_id, component_source):
        market_name = component_source.get_market_name()
        install_from_cloud = component_source.is_install_from_cloud()
        if install_from_cloud and market_name:
            market = app_market_repo.get_app_market_by_name(enterprise_id, market_name, raise_exception=True)
            versions = app_market_service.get_market_app_model_versions(market, component_source.group_key)
        else:
            versions = rainbond_app_repo.get_rainbond_app_versions(enterprise_id, component_source.group_key)
        return versions


market_app_service = MarketAppService()
