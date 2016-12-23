$(function () {
    //打开新增端口号窗口
    $(".openAdd").on("click",function(){
        $(".addPort").css({"display":"table-row"});
    });
    //确定添加端口号
    $(".add").on("click",function(){
        var portNum = parseInt($(".add_port").val());
        if( portNum>0 && portNum<65535 )
        {
            var addOnoff = true;
            var portLen = $(".portNum").length;
            for( var i = 0; i<portLen; i++ )
            {
                if( portNum == $(".portNum").eq(i).html() )
                {
                    addOnoff = false;
                    break;
                }
            }
            if( addOnoff )
            {
                var newTr = document.createElement("tr");
                var arr = ['Http','Stream'];
                var oTr = '<tr><td><a href="javascript:void(0);" class="portNum edit-port">'+$(".add_port").val()+'</a></td>';
                oTr += '<td><select data-port-http="'+$(".add_port").val()+'Http">';
                for( var i = 0; i < 2; i++ )
                {
                    if( $('.add_http').val() == arr[i] )
                    {
                        oTr += '<option selected="selected">'+arr[i]+'</option>';
                    }
                    else{
                        oTr += '<option>'+arr[i]+'</option>';
                    }
                }
                oTr += '</select></td>';
                if( $("#addInner").prop("checked") == true )
                {
                    oTr += '<td><div class="checkbox"><input type="checkbox" name="" value="" id="'+$(".add_port").val()+'inner" checked="true" /><label class="check-bg" for="'+$(".add_port").val()+'inner"></label></div></td>';
                }
                else{
                    oTr += '<td><div class="checkbox"><input type="checkbox" name="" value="" id="'+$(".add_port").val()+'inner" /><label class="check-bg" for="'+$(".add_port").val()+'inner"></label></div></td>';
                }
                if( $("#addOuter").prop("checked") == true )
                {
                    oTr += '<td><div class="checkbox"><input type="checkbox" name="" value="" id="'+$(".add_port").val()+'inner" checked="true" /><label class="check-bg" for="'+$(".add_port").val()+'outer"></label></div></td>';
                }
                else{
                    oTr += '<td><div class="checkbox"><input type="checkbox" name="" value="" id="'+$(".add_port").val()+'inner" /><label class="check-bg" for="'+$(".add_port").val()+'outer"></label></div></td>';
                }
                oTr += '<td><img class="rubbish" src="/static/www/images/rubbish.png"/></td></tr>';
                newTr.innerHTML = oTr;
                $(oTr).appendTo(".port");
                $(".addPort").css({"display":"none"});
                delPort();
                editPort();
            }
            else{
                alert("端口号冲突～～");
            }
        }
        else{
            alert("请输入正确的端口号～～");
        }
        $(".add_port").val("");
    });
    //取消端口号的添加
    $(".noAdd").on("click",function(){
        $(".addPort").css({"display":"none"});
    });
    delPort();
    //删除端口号与环境变量
    function delPort(){
        $("img.rubbish").on("click",function(){
            $(this).parents("tr").remove();
        })
    }
    delLi();
    //删除依赖与目录
    function delLi(){
        $("img.delLi").on("click",function(){
            $(this).parents("li").remove();
        })
    }
    //修改端口号
    editPort();
    function editPort(){
        $('.edit-port').editable({
            type: 'text',
            pk: 1,
            success: function (data) {
                //window.location.reload();
            },
            error: function (data) {
                msg = data.responseText;
                res = $.parseJSON(msg);
                showMessage(res.info);
            },
            ajaxOptions: {
                beforeSend: function(xhr, settings) {
                    xhr.setRequestHeader("X-CSRFToken", $.cookie('csrftoken'));
                    settings.data += '&action=change_port';
                },
            }
        });
    }
    //显示添加环境变量内容
    $(".openAddEnviroment").on("click",function(){
        $(".addContent").css({"display":"table-row"});
    });
    $(".addEnviroment").on("click",function(){
        if( $(".enviroKey").val() && $(".enviroValue").val() && $(".enviroName").val() )
        {
            var len = $(".enviromentKey").length;
            var onOff = true;
            for( var i = 0; i<len; i++ )
            {
                if( $(".enviroKey").val() == $(".enviromentKey")[i].innerHTML ){
                    alert("变量名冲突～～");
                    onOff = false;
                    break;
                }
            }
            if( onOff )
            {
                var str = '<tr><td><a href="javascript:void(0);" class="enviromentName edit-port">'+$(".enviroName").val()+'</a></td>';
                str += '<td><a href="javascript:void(0);" class="edit-port enviromentKey key'+(len+1)+'">'+$(".enviroKey").val()+'</a></td>';
                str += '<td><a href="javascript:void(0);" class="edit-port enviromentValue value'+(len+1)+'">'+$(".enviroValue").val()+'</a></td>';
                str += '<td><img class="rubbish" src="/static/www/images/rubbish.png"/></td></tr>';
                $(str).appendTo(".enviroment");
                $(".enviroName").val('');
                $(".enviroKey").val('');
                $(".enviroValue").val('');
                $(".addContent").css({"display":"none"});
                delPort();
            }
        }
        else{
            console.log(2);
        }
    });
    $(".noAddEnviroment").on("click",function(){
        $(".addContent").css({"display":"none"});
        $(".enviroKey").val('');
        $(".enviroValue").val('');
    });
    //打开弹出层，选择服务依赖
    $(".addDepend").on("click",function(){
        $(".above").css({"display":"block"});
    })
    //关闭弹出层
    $("button.cancel").on("click",function(){
        $(".above").css({"display":"none"});
    });
    $(".del").on("click",function(){
        $(".above").css({"display":"none"});
    });
    $(".sure").on("click",function(){
        var len = $(".depend input").length;
        for( var i = 0; i<len; i++ )
        {
            if( $(".depend input")[i].checked )
            {
                var appNameLen = $("a.appName").length;
                var onOff = true;
                for( var j = 0; j<appNameLen; j++ )
                {
                    if( $("a.appName")[j].innerHTML == $(".depend input")[i].getAttribute("data-action") )
                    {
                        onOff = false;
                        break;
                    }
                }
                if( onOff )
                {
                    var str = '';
                    str += '<li><a href="javascript:void(0);" class="appName">'+$(".depend input")[i].getAttribute("data-action")+'</a>';
                    str += '<img src="/static/www/images/rubbish.png" class="delLi"/></li>';
                    $(str).appendTo(".applicationName");
                    delLi();
                }
            }
        }
        $(".above").css({"display":"none"});
    });

    //新设持久化目录
    $(".addCata").on("click",function(){
        $("p.catalogue").css({"display":"block"});
    })
    $(".addCatalogue").on("click",function(){
        if( $(".catalogueContent").val() )
        {
            var str = '<li><a href="javascript:void(0);" class="path_name">/app/'+$(".catalogueContent").val()+'</a>';
            str += '<img src="/static/www/images/rubbish.png" class="delLi"/></li>';
            $(str).appendTo(".fileBlock ul.clearfix");
            $("p.catalogue").css({"display":"none"});
            $(".catalogueContent").val("");
            delLi();
        }
        else{
            alert("请输入目录～～");
        }
    });
    $(".noAddCatalogue").on("click",function(){
        $("p.catalogue").css({"display":"none"});
    });

    //点击"下一步"，提交内容
    $(".submit").on("click",function(){
        var portLen = $("tbody.port tr").length;
        var portArr = [];
        for( var i = 0; i<portLen; i++ )
        {
            var port_json = {};
            port_json["container_port"] = $("tbody.port tr").eq(i).find("td").eq(0).children("a").html();
            port_json["protocol"] = $("tbody.port tr").eq(i).find("td").eq(1).children("select").val();
            port_json["is_inner_service"] = $("tbody.port tr").eq(i).find("td").eq(2).find("input").prop("checked")?1:0;
            port_json["is_outer_service"] = $("tbody.port tr").eq(i).find("td").eq(3).find("input").prop("checked")?1:0;
            portArr[i] = port_json;
        }
        //console.log(JSON.stringify(portArr));

        var appLen = $(".path_name").length;
        var appArr = [];
        for( var j = 0; j<appLen; j++ )
        {
            var app_json = {};
            app_json["volume_path"] = $(".path_name").eq(j).html();
            appArr[j] = app_json;
        }
        //console.log(JSON.stringify(appArr));

        var enviromentLen = $(".enviromentName").length;
        var enviromentArr = [];
        for( var k = 0; k<enviromentLen; k++ )
        {
            var enviroment_json = {};
            enviroment_json["name"] = $("tbody.enviroment tr").eq(k).find("td").eq(0).children("a").html();
            enviroment_json["attr_name"] = $("tbody.enviroment tr").eq(k).find("td").eq(1).children("a").html();
            enviroment_json["attr_value"] = $("tbody.enviroment tr").eq(k).find("td").eq(2).children("a").html();
            enviromentArr[k] = enviroment_json;
        }
        //console.log(JSON.stringify(enviromentArr));

        var service_config = {
            "port_list" : JSON.stringify(portArr),
            "env_list" : JSON.stringify(enviromentArr),
            "volume_list" : JSON.stringify(appArr)
        }
        console.log(service_config);
    })

});