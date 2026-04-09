# Shipping

这个仓库现在同时保留原来的 Python / Streamlit 文件，并新增了一个不依赖 Streamlit 的静态网页入口：`index.html`。

## 现在推荐的部署方式

使用 GitHub Pages 发布静态页面，不会像 Streamlit Community Cloud 那样因为闲置进入休眠。

目标访问地址：

- `https://tyawosoo.github.io/shipping/`

## 功能

- 按省 / 市 / 区县查询线路
- 选择寄出日期，自动计算下次发车时间
- 支持手动设置附加运输天数
- 自动生成可复制的分享文案
- 支持手机和电脑浏览器

## 说明

页面预测基于班次表，不是签收历史，因此结果属于业务估算值。
