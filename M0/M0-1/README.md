## 创意组一轮考核M0-1
# 完成过程
- 通过搜索引擎在各个网站（如CSDN、知乎、以及相关软件的官网）上翻阅资料，并利用AI工具辅助解决出错的地方。
- 查阅的资料包括一些软件的安装命令、命令报错的原因。（相关学习链接：https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debs.html 、https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debs.html 、https://zhuanlan.zhihu.com/p/137114974 、https://blog.csdn.net/qq_42417071/article/details/138501673 、 https://uv.doczh.com/getting-started/installation/ 、 https://zhuanlan.zhihu.com/p/423066660 、https://www.runoob.com/git/git-push.html）
- 完成了ubuntu在VMware虚拟机上的部署，并配置了ROS2、vscode的开发环境。完成ssh的配置，并成功搭建起git仓库。
# 本机踩坑实录
1. 上传git仓库时报错，提示无法读取远程仓库。解决方法：比对命令【(https://zhuanlan.zhihu.com/p/423066660)同时利用AI工具排查】发现用户名输错，然后更改命令里面的用户名。
2. 登陆github时提示邮箱不合法，登不上去。解决方案：换一个github账号重新操作。
3. python虚拟环境尝试搭建了却识别不出来。解决方案：查阅资料：https://developer.aliyun.com/article/1597982。利用其中的方法解决。
4. ”当前目录不在git仓库里“。解决方案：查阅资料：https://juejin.cn/post/7292217232188686390。查找命令执行目录，将测试文件放入git仓库的文件位置