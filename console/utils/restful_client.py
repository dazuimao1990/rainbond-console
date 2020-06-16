# -*- coding: utf8 -*-
import os
import logging
from functools import wraps

from console.exception.main import ServiceHandleException
import market_client
from market_client.configuration import Configuration
import openapi_client as store_client
from openapi_client.rest import ApiException
from openapi_client.configuration import Configuration as storeConfiguration

logger = logging.getLogger("default")

# def get_market_client(enterpriseID, enterpriseToken, host=None):
#     configuration = Configuration()
#     configuration.host = host if host else os.environ.get('APP_CLOUD_API', 'http://api.goodrain.com:80')
#     configuration.api_key['X_ENTERPRISE_TOKEN'] = enterpriseToken
#     configuration.api_key['X_ENTERPRISE_ID'] = enterpriseID
#     # create an instance of the API class
#     return market_client.AppsApi(market_client.ApiClient(configuration))


def get_default_market_client():
    configuration = Configuration()
    configuration.host = os.environ.get('APP_CLOUD_API', 'http://api.goodrain.com:80')
    # create an instance of the API class
    return market_client.AppsApi(market_client.ApiClient(configuration))


def get_market_client(access_key, host=None):
    configuration = storeConfiguration()
    configuration.host = host if host else os.environ.get('APP_CLOUD_API', 'http://api.goodrain.com:80')
    configuration.api_key['Authorization'] = access_key
    return store_client.MarketOpenapiApi(store_client.ApiClient(configuration))


def apiException(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ApiException as e:
            logger.debug(e)
            if e.status == 403:
                raise ServiceHandleException("no cloud permission", msg_show="未进行授权", status_code=403, error_code=10407)
            if e.status == 404:
                raise ServiceHandleException("no found market", msg_show="资源不存在", status_code=404)
            if str(e.status)[0] == '4':
                raise ServiceHandleException(msg=e.message, msg_show="获取数据失败，参数错误", status_code=e.status)
            raise ServiceHandleException(msg="call cloud api failure", msg_show="请求失败，请检查网络和配置", status_code=500)
        except ValueError as e:
            logger.debug(e)
            raise ServiceHandleException(
                msg="return data can`t be serializer", msg_show="数据不能被序列化，请检查配置或参数是否正确", status_code=500)

    return wrapper
