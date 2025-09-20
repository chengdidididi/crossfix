# 跨页修正工具
> 由于市面上对de-drm的漫画电子档案、及扫图文件的跨页适配功能参差不齐，所以简单实现了这个项目，可以往zip文件里放一个空白扉页，从而使所有支持双页的漫画阅读器都能正常显示跨页

## 功能支持
- **插入扉页** 自动插入一个与封面后第二张图片尺寸一致的全白图片
- **删除扉页** 考虑到误操作，可以在插入扉页后通过该功能简单地撤回扉页插入

## 使用

#### 本地构建
1、clone到本地并cd到文件夹
```bash
git clone https://github.com/chengdidididi/crossfix.git
cd [项目文件夹]
```
2、安装依赖
```bash
pip install -r requirements.txt
```
3、通过gui.py运行程序
```bash
python gui.py
```

#### 使用打包好的exe文件
请在release中下载
