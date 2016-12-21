$(function(){
    //// ww-2016-12-6 选择 groupname start
    //弹出层
    function FnLayer(textTit){
        var oDiv = '<div class="layerbg"><div class="layermain"></div></div>';
        var oCloseBtn = '<a href="javascript:;" class="closebtn fn-close">X</a>';
        var oTit = '<p class="layer-tit">'+ textTit +'</p>';
        var oInput ='<p class="input-css"><input name="" type="text" value="" /></p>';
        var oLink = '<p class="layerlink"><a href="javascript:;" class="fn-sure">确定</a><a href="javascript:;" class="fn-close">取消</a></p>';
        $("body").append(oDiv);
        $("div.layermain").append(oCloseBtn,oTit);
        $("div.layermain").append(oInput);
        $("div.layermain").append(oLink);
        $(".fn-close").click(function(){
             $("div.layerbg").remove();
             $(".input-css input").prop("value","");
             $("#group-name").find("option[value='-1']").prop("selected",true);
        });
        $(".fn-sure").click(function(){
            if(inputText == ""){
                swal("您还没有输入组名！")
                return false;
            }else{
                var inputText = $(".input-css input").val();
                var tenant_name = $("#currentTeantName").val();
                ///ajax start

                $.ajax({
                    type : "post",
                    url : "/ajax/" + tenant_name  + "/group/add",
                    data : {
                        group_name : inputText
                    },
                    cache : false,
                    beforeSend : function(xhr, settings) {
                        var csrftoken = $.cookie('csrftoken');
                        xhr.setRequestHeader("X-CSRFToken", csrftoken);
                    },
                    success : function(msg) {
                        if(msg.ok){
                            var  group_id = msg.group_id;
                            var  group_name = msg.group_name;
                            var  Option = "<option value=" +  group_id + ">" + group_name + "</option>";
                            $("div.layerbg").remove();
                            $(".input-css input").prop("value","");
                            $("#group-name option").eq(0).after(Option);
                            $("#group-name option").each(function(){
                                var oVal = $(this).prop("value");
                                if(oVal == group_id){
                                    $(this).prop("selected",true);
                                }
                            });
                        }else{
                            swal(msg.info);
                        }
                    },
                    error : function() {
                        swal("系统异常,请重试");
                    }
                });
                
                ///ajax end
            }
              
        });   
    }
    //  弹出层
    $("#group-name").change(function(){
     var groupName=$("#group-name option:selected").val();
        //console.log(groupName);
        if(groupName == -2) {
            FnLayer("请输入新增组名");  
        }
    });
    //// ww-2016-12-6 选择 groupname end 
    
	// 滑块 开始 
	function FnRange(inputid,textid,widid,num){
		var range= document.getElementById(inputid);
		var result = document.getElementById(textid);
		var wid = document.getElementById(widid);
        var maxnum = range.getAttribute("max");
		cachedRangeValue = /*localStorage.rangeValue ? localStorage.rangeValue :*/ num; 
		// 检测浏览器
		var o = document.createElement('input');
	    o.type = 'range';
	    if ( o.type === 'text' ) alert('不好意思，你的浏览器还不够酷，试试最新的浏览器吧。');
	    range.value = cachedRangeValue;
	    wid.style.width = (range.value-num)/(maxnum-num)*100 + "%";
	    range.addEventListener("mouseup", function() {
            if(inputid == "OneMemory"){
                if(range.value >= 128 && range.value < 256){
                    result.innerHTML = "128M";
                }else if(range.value >= 256 && range.value < 512){
                    result.innerHTML = "256M";
                }else if(range.value >= 512 && range.value < 1024){
                    result.innerHTML = "512M";
                }else if(range.value >= 1024 && range.value < 2048){
                    result.innerHTML = "1G";
                }else if(range.value >= 2048 && range.value < 3072){
                    result.innerHTML = "2G";
                }else if(range.value >= 3072 && range.value < 4096){
                    result.innerHTML = "3G";
                }else if(range.value >= 4096 && range.value < 5120){
                    result.innerHTML = "4G";
                }else if(range.value >= 5120 && range.value < 6144){
                    result.innerHTML = "5G";
                }else if(range.value >= 6144 && range.value < 7168){
                    result.innerHTML = "6G";
                }else if(range.value >= 7168 && range.value < 8100){
                   result.innerHTML = "7G";
                }else{
                   result.innerHTML = "8G";
                }
            }else{
               result.innerHTML = range.value; 
            }
	        wid.style.width = (range.value-num)/(maxnum-num)*100 + "%";
	        //alert("你选择的值是：" + range.value + ". 我现在正在用本地存储保存此值。在现代浏览器上刷新并检测。");
	        //localStorage ? (localStorage.rangeValue = range.value) : alert("数据保存到了数据库或是其他什么地方。");
	        //result.innerHTML = range.value;
            FnPrice();
	    }, false);
	    // 滑动时显示选择的值
	    range.addEventListener("input", function() {
            if(inputid == "OneMemory"){
                if(range.value >= 128 && range.value < 256){
                    result.innerHTML = "128M";
                }else if(range.value >= 256 && range.value < 512){
                    result.innerHTML = "256M";
                }else if(range.value >= 512 && range.value < 1024){
                    result.innerHTML = "512M";
                }else if(range.value >= 1024 && range.value < 2048){
                    result.innerHTML = "1G";
                }else if(range.value >= 2048 && range.value < 3072){
                    result.innerHTML = "2G";
                }else if(range.value >= 3072 && range.value < 4096){
                    result.innerHTML = "3G";
                }else if(range.value >= 4096 && range.value < 5120){
                    result.innerHTML = "4G";
                }else if(range.value >= 5120 && range.value < 6144){
                    result.innerHTML = "5G";
                }else if(range.value >= 6144 && range.value < 7168){
                    result.innerHTML = "6G";
                }else if(range.value >= 7168 && range.value < 8100){
                   result.innerHTML = "7G";
                }else{
                   result.innerHTML = "8G";
                }
            }else{
               result.innerHTML = range.value; 
            }
	        wid.style.width = (range.value-num)/(maxnum-num)*100 + "%";

	    }, false);
	}
    
    FnRange("OneMemory","OneMemoryText","OneMemoryWid",128);
    FnRange("NodeNum","NodeText","NodeWid",1);
    FnRange("Disk","DiskText","DiskWid",1);
    FnRange("TimeLong","TimeLongText","TimeLongWid",1);
    
   
   
    
    // 滑动框 结束
    
    //计算价格
    var before_memory= $("#price-box").attr("data-before-memory");
    var before_disk= $("#price-box").attr("data-before-disk");
    var before_net= $("#price-box").attr("data-before-net");
    var after_memory= $("#price-box").attr("data-after-memory");
    var after_disk= $("#price-box").attr("data-after-disk");
    var after_net= $("#price-box").attr("data-after-net");
    $("#aft-memory").html(after_memory);
    $("#aft-disk").html(after_disk);
    $("#aft-net").html(after_net);

    FnPrice();

    function FnPrice(){
        var  memory_num = parseInt(document.getElementById("OneMemoryText").innerHTML);
        if(memory_num > 10){
            memory_num = memory_num / 1024;
        }
        var node_num = parseInt(document.getElementById("NodeText").innerHTML);
        var Disk_num = parseInt(document.getElementById("DiskText").innerHTML);
        var time_num = parseInt(document.getElementById("TimeLongText").innerHTML);
        var memory_onoff = document.getElementById("MoneyBefore").checked;
        var disk_onoff = document.getElementById("DiskBefore").checked;
        var onehour;
        //计算
        if(memory_onoff == true && disk_onoff == true){
            onehour = before_memory * memory_num  +  before_disk * Disk_num;
            Fnmemory();
        }else if(memory_onoff == true && disk_onoff != true){
            onehour = before_memory * memory_num;
            Fnmemory();
        }else if(memory_onoff != true && disk_onoff == true){
            onehour = before_disk * Disk_num;
            Fnmemory();
        }else{
            onehour = 0;
            Fnmemory();
        }
        //计算 
        function Fnmemory(){
            var total_money= onehour * 24 * time_num  *30 * 4 * node_num;
            var buy_money;
            if(time_num>=12){
                buy_money = onehour * 24 * time_num *1.5 *30;
            }else{
                buy_money = onehour * 24 * time_num *2*30;
            }
            $("#need-money").html(total_money.toFixed(2));
        }
    }
    ///
    function toDecimal2(x){
        var f = parseFloat(x);
        if (isNaN(f)) {
            return false;
        }
        var f = Math.round(x * 100) / 100;
        var s = f.toString();
        var rs = s.indexOf('.');
        if (rs < 0) {
            rs = s.length;
            s += '.';
        }
        while (s.length <= rs + 2) {
            s += '0';
        }
        return s;
    }
    ///
    // 计算价格结束

    // 显示 隐藏
    $("#MoneyBefore").change(function(){
        var onoff = $("#MoneyBefore").prop("checked");
        if(onoff == true){
            // $(".fn-memory-node").show();
            $("#aft-memory-box").hide();
        }else{
            //$(".fn-memory-node").hide();
            $("#aft-memory-box").show();
        }
        FnPrice();
    });
    $("#MoneyAfter").change(function(){
        
        var onoff = $("#MoneyAfter").prop("checked");
        if(onoff == false){
            //$(".fn-memory-node").show();
            $("#aft-memory-box").hide();
        }else{
            //$(".fn-memory-node").hide();
            $("#aft-memory-box").show();
        }
        FnPrice();
    });
    $("#DiskBefore").change(function(){
        var onoff = $("#DiskBefore").prop("checked");
        if(onoff == true){
            $(".fn-disk").show();
            $("#aft-disk-box").hide();
        }else{
            $(".fn-disk").hide();
            $("#aft-disk-box").show();
        }
        FnPrice();
    });
    $("#DiskAfter").change(function(){
        var onoff = $("#After").prop("checked");
        if(onoff == false){
            $(".fn-disk").show();
            $("#aft-disk-box").hide();
        }else{
            $(".fn-disk").hide();
            $("#aft-disk-box").show();
        }
        FnPrice();
    });
    // 输入框输入样式

    // 01 输入用户名
    $('#create_name').blur(function(){
        var appName = $(this).val();
        //var checkReg = /^[a-z][a-z0-9-]*[a-z0-9]$/;
        //var result = true;
        if(appName == ""){
            $('#create_name_notice').slideDown();
            return;
        }else{
            $('#create_name_notice').slideUp();
        }
    });
    // 01 end 

    //03 公开项目
    $('#service_code_url').blur(function(){
        var appurl= $(this).val();
        if(appurl == ""){
            $('#service_code_url_tips').slideDown();
            return;
        }else{
            $('#service_code_url_tips').slideUp();
        }
    });
    //03 公开项目
    //04 自建Git
    $('#my_git_url').blur(function(){
        var myurl= $(this).val();
        if(myurl == ""){
            $('#my_git_url_tips').slideDown();
            return;
        }else{
            $('#my_git_url_tips').slideUp();
        }
    });
    //04 自建Git
    // github 

    var way_value = $(".fn-way").attr("data-action");
    if(way_value == "gitlab_exit"){
        $('#service_code_from').val("gitlab_exit");
        var tenantName= $('#currentTeantName').val();
        _url = "/ajax/"+tenantName+"/code_repos?action=gitlab";
        loadObj(_url);
    }else if(way_value == "github"){
        $('#service_code_from').val("github");
        var tenantName= $('#currentTeantName').val();
        _url = "/ajax/"+tenantName+"/code_repos?action=github";
        loadObj(_url);
    }else{
        //return;
        console.log("");
    }
     
    //项目 地址
    function loadObj(_url){
        var listWrap;
        var service_code_from = $('#service_code_from').val();
        
        $.ajax({
            type: "GET",
            url: _url,
            cache: false,
            success: function(msg){
                var dataObj = msg;
                if(dataObj["status"] == "unauthorized"){
                    window.open(dataObj["url"], "_parent");
                }else if(dataObj["status"]=="success"){
                    var dataList=dataObj["data"];
                    var htmlmsg="";
                    for(var i=0;i<dataList.length;i++){
                        data = dataList[i];
                        htmlmsg +='<option idx="'+ i +'" data="'+data["code_id"]+ '" id="repos_'+data["code_id"] + '" name="repos_'+data["code_id"]+'" value='+data["code_repos"] +'">';
                        htmlmsg += data["code_user"]+'/'+data["code_project_name"] + '</option>';
                    }
                    if(service_code_from == "github"){
                        listWrap = $("#code_github_list");
                        if(htmlmsg){
                            $("#waiting").hide();
                            $("#Githubbox").show();
                            $(listWrap).html(htmlmsg);
                        }
                    }else{
                        listWrap = $("#code_gr_list");
                        if(htmlmsg){
                            htmlmsg += '<option value="newobj">新建项目</option>';
                            $("#gitlabbox").show();
                            $("#waiting").hide();
                            $(listWrap).html(htmlmsg);
                        }else{
                            $(listWrap).html('<option value="newobj">新建项目</option>'); 
                            $("#gitlabbox").show();
                            $("#waiting").hide();
                        }
                    }                    

                    var grbranch = $("#code_gr_list option:selected").attr("value");
                    
                    if(grbranch == "newobj"){
                        $("#gr_branchbox").hide();
                    }else{
                        $("#gr_branchbox").show();
                    }
                    var sedoption = $(listWrap).children("option:selected");
                    var service_code_id=$(sedoption).attr("data");
                    var clone_url = $('#repos_'+service_code_id).val();
                    Fnbranch(service_code_from,service_code_id,clone_url);
                    
                                       
                    $(listWrap).change(function(){
                        var sedoption = $(listWrap).children("option:selected");
                        var service_code_id=$(sedoption).attr("data");
                        var clone_url = $('#repos_'+service_code_id).val();
                        Fnbranch(service_code_from,service_code_id,clone_url); 
                        if(grbranch == "newobj"){
                            $("#gr_branchbox").hide();
                        }else{
                            $("#gr_branchbox").show();
                        } 
                    });
                }else{
                    $('#waiting').html("无可用仓库");
                }
            },
            error: function(){
                console.log("系统异常");
            }
        });
    }
    //项目 地址

    // 项目分支 
    function  Fnbranch(code_from,code_id,clone_url){
        var action="";
        var user ="";
        var repos ="";
        var branch_box;
        if(code_from=="gitlab_exit"){
            action="gitlab";
            branch_box = $("#gr_branch");
        }else if(code_from=="github"){
            action="github";
            user =  clone_url.split("/")[3];
            repos = clone_url.split("/")[4].split(".")[0];
            branch_box = $("#gh_branch");
        }
        var tenantName= $('#currentTeantName').val();
        //
        if(action != ""){
            ///
            $.ajax({
                type : "POST",
                url : "/ajax/"+tenantName+"/code_repos",
                data : "action=" + action + "&code_id="+code_id+"&user="+user+"&repos="+repos,
                cache : false,
                beforeSend : function(xhr, settings) {
                    var csrftoken = $.cookie('csrftoken');
                    xhr.setRequestHeader("X-CSRFToken", csrftoken);
                },
                success : function(msg) {
                    var dataObj = msg;
                    if(dataObj["status"] == "unauthorized") {
                        window.open(dataObj["url"],"_parent");
                    }else if(dataObj["status"] == "success"){
                        var dataList=dataObj["data"];
                        var htmlmsg="";
                        var codeId = dataObj['code_id'];
                        for(var i=0;i<dataList.length;i++){
                            data = dataList[i];
                            htmlmsg +='<option value="'+data["version"]+'">'+data["version"]+'</option>';
                        }
                        var htmlno = '<option value="0">暂无可选分支</option>';
                        if(htmlmsg){
                            $(branch_box).html(htmlmsg);
                        }else{
                            $(branch_box).html(htmlno);
                        }  
                    }else {
                       swal("操作失败");
                    }
                },
                error : function() {
                    console.log("系统异常");
                }
            });
            ///
        }
        //
    }
    //项目分支 

    //提交 
    $("#BtnFirst").click(function(){
        var appname = $("#create_name").val();
        var groupname = $("#group-name option:selected").html();
        var groupid = $("#group-name option:selected").attr("value");
        var service_code_from = "gitlab_new";
        var myWay = $(".fn-way").attr("data-action");
        var code_url;
        var code_id;
        var code_branch;
        var code_branch_id;
        var memory_onoff = $("#MoneyBefore").prop("checked");
        var disk_onoff = $("#DiskBefore").prop("checked");
        if(memory_onoff == true && disk_onoff == true){
            var memory_num = parseInt($("#OneMemoryText").html());
            var node_num = parseInt($("#NodeText").html());
            var disk_num = parseInt($("#NodeText").html());
            var time_num = parseInt($("#TimeLongText").html());
        }else if(memory_onoff == true && disk_onoff == false ){
            var memory_num = parseInt($("#OneMemoryText").html());
            var node_num = parseInt($("#NodeText").html());
            var disk_num = 0;
            var time_num = parseInt($("#TimeLongText").html());
        }else if(memory_onoff == false && disk_onoff == true){
            var memory_num = 0;
            var node_num = 0;
            var disk_num = parseInt($("#NodeText").html());
            var time_num = parseInt($("#TimeLongText").html());
        }else{
            var memory_num = 0;
            var node_num = 0;
            var disk_num = 0;
            var time_num = 0;
        }
        if(appname == ""){
            $("#create_name_notice").show();
            return;
        }else{
            $("#create_name_notice").hide();
        }
        if(myWay == "gitlab_manual"){
            service_code_from = "gitlab_manual";
            //01
            code_url =$("#service_code_url").val(); 
            if(code_url == ""){
                $("#service_code_url_tips").show();
                return;
            }else{
                $("#service_code_url_tips").hide();
            }
            //01
        }else if(myWay == "gitlab_new"){
            service_code_from = "gitlab_new";
            //02
            code_url =$("#my_git_url").val(); 
            if(code_url == ""){
                $("#my_git_url_tips").show();
                return;
            }else{
                $("#my_git_url_tips").hide();
            }
            //02
        }else if(myWay == "github"){
            service_code_from = "github";
            //03
            code_id = $("#code_github_list").attr("date");
            if(code_id == "-1"){
                return;
            }else{
                code_url =$("#code_github_list option:selected").val();
                code_id = $("#code_github_list option:selected").attr("data"); 
                code_branch = $("#gh_branch option:selected").val();
                code_branch_id = $("#gh_branch option:selected").attr("data");
            }
            //03
        }else if(myWay == "gitlab_exit"){
            service_code_from = "gitlab_exit";
            //04
            code_id = $("code_gr_list").attr("date");
            if(code_id == "-1"){
                return;
            }else{
                code_url =$("#code_gr_list option:selected").val();
                code_id = $("#code_gr_list option:selected").attr("data"); 
                code_branch = $("#gr_branch option:selected").val();
                code_branch_id = $("#gr_branch option:selected").attr("data");
            }
            //04
        }else if(myWay == "gitlab_demo"){
            service_code_from = "gitlab_manual";
            //05
            code_url = $("#Democode option:selected").val();
            code_branch = $("#Demobranch option:selected").val();
            //05
        }else{
            return;
        }
        console.log(myWay);
        console.log(appname + "--" + groupname + "--" + groupid + "--" + code_url + "--" + code_id + "--" +code_branch + "--" + code_branch_id + "///" +  memory_onoff + "--" +  disk_onoff + "///" + memory_num + "--" + node_num + "--" + disk_num + "--" + time_num);
        ///
        $("#BtnFirst").attr('disabled', true);
        var tenantName= $('#currentTeantName').val();
        $.ajax({
            type : "post",
            url : "/apps/" + tenantName + "/app-create/",
            data : {
                "create_app_name" : appname,
                "groupname" : groupname,
                "select_group_id" : groupid,
                "service_code_from":service_code_from,
                "service_code_clone_url" : code_url,
                "service_code_id" : code_id,
                "service_code_version" : code_branch,
                "memory_pay_method" : memory_onoff ? "prepaid":"postpaid",
                "disk_pay_method" : disk_onoff ? "prepaid":"postpaid",
                "service_min_memory" : memory_num,
                "service_min_node" : node_num,
                "disk_num" : disk_num,
                "pre_paid_period" : time_num
            },
            cache : false,
            beforeSend : function(xhr, settings) {
                var csrftoken = $.cookie('csrftoken');
                xhr.setRequestHeader("X-CSRFToken", csrftoken);
            },
            success : function(msg) {
                var dataObj = msg;
                if (dataObj["status"] == "exist") {
                    swal("服务名已存在");
                } else if (dataObj["status"] == "owed"){
                    swal("余额不足请及时充值")
                } else if (dataObj["status"] == "expired"){
                    swal("试用已到期")
                } else if (dataObj["status"] == "over_memory") {
                    swal("资源已达上限，不能创建");
                } else if (dataObj["status"] == "over_money") {
                    swal("余额不足，不能创建");
                } else if (dataObj["status"] == "empty") {
                    swal("应用名称不能为空");
                }else if (dataObj["status"] == "code_from") {
                    swal("应用资源库未选择");
                }else if (dataObj["status"] == "code_repos") {
                    swal("代码仓库异常");
                }else if (dataObj["status"] == "success") {
                    service_alias = dataObj["service_alias"]
                    window.location.href = "/apps/" + tenantName + "/" + service_alias + "/app-dependency/";
                } else {
                    swal("创建失败");
                }
                $("#BtnFirst").attr('disabled', false);
            },
            error : function() {
                swal("系统异常,请重试");
                $("#BtnFirst").attr('disabled', false);
            }
        });
        ///

    });

    
    //tips
    $(".fn-tips").mouseup(function(){
        var tips = $(this).attr("data-tips");
        var x = $(this).offset().left;
        var y = $(this).offset().top;
        var oDiv='<div class="tips-box"><p><span>'+ tips +'</span><cite></cite></p></div>';
        $("body").append(oDiv);
        $(".tips-box").css({"left":x + 10,"top":y-5});
    });
    $(".fn-tips").mouseout(function(){
        $(".tips-box").remove();
    });
})










