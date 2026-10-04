# MAE：从真实论文到方法配图

[English](README.md) · **简体中文**

![MAE 掩码自编码器的 Pastel 方法图](mae/figure.png)

**论文：**Kaiming He、Xinlei Chen、Saining Xie、Yanghao Li、Piotr Dollar、Ross Girshick，*Masked Autoencoders Are Scalable Vision Learners*，CVPR 2022，16000-16009 页。[官方会议论文集](https://openaccess.thecvf.com/content/CVPR2022/html/He_Masked_Autoencoders_Are_Scalable_Vision_Learners_CVPR_2022_paper.html) · [论文 PDF](https://openaccess.thecvf.com/content/CVPR2022/papers/He_Masked_Autoencoders_Are_Scalable_Vision_Learners_CVPR_2022_paper.pdf)

项目直接读取官方 PDF 中的 **第 3 节 Approach**，将论文的非对称预训练过程转化为图像：编码器只接收可见图像块，编码后才加入共享遮挡标记，解码器预测像素，重建损失仅计算遮挡区域。

## 图里每个元素的含义

- **图像块包含具体内容。** 同一辆红色自行车贯穿原图、保留的局部图像和预测示意图。
- **编码器输入是稀疏的。** 示意网格的 16 块中保留 4 块，展示 75% 遮挡。
- **特征不是原图裁块。** 编码后使用 `z3`、`z6`、`z12`、`z13` 表示对应位置的特征。
- **遮挡向量是共享的。** 12 个缺失位置填入同一个学习向量 `M`，再为所有 token 加入解码器位置编码。
- **监督路径明确。** 原图目标与预测像素在遮挡块 MSE 处汇合，可见区域不参与损失计算。

自行车画面和 4 × 4 网格是解释方法的原创绘图选择，不是论文中的重建实验结果，也没有使用论文原图。

## 在工作台中生成

1. 下载上方官方 PDF，新建项目并上传论文。
2. 选择 **3. Approach**。本次解析结果中的零基章节索引为 `11`，对应 PDF 第 3-4 页；所选章节完整进入上下文。
3. 选择 **Pastel、Quality、ML TopConf (Seaborn Deep)、整体框架图**，数量为 1；使用 [request.json](mae/request.json) 中的需求。
4. 生成并审阅提示词和带原文引用的 FigureSpec。本次第 2 次修订将画布统一为 **3840 × 2160、16:9**，没有改变科学结构。
5. 使用 **4K、16:9、Quality** 生成图片并检查。
6. 本例进行了两次参考图编辑，第二次使用连线区域蒙版；[首次编辑指令](mae/edit-instruction.txt)、[蒙版编辑指令](mae/connector-instruction.txt)和[初始 PNG](mae/initial.png)一并提供。
7. 在仓库根目录运行 `uv run --project backend --locked python docs/demo/layout_mae.py`，将已保存的素材排成 **4800 × 1920、5:2** 成品。这个案例专用脚本复用生成的自行车图块，在本地定位模块、文字和连线端点。

也可以将 [prompt.txt](mae/prompt.txt) 粘贴到快捷生成，选择相同风格、配色和尺寸。不同次生成的布局可能有所变化。

## 生成记录

| 阶段 | 本次实际配置 |
| --- | --- |
| 来源 | CVPR 2022 官方 PDF，第 3 节，所选章节完整覆盖 |
| 提示词 | `gpt-6-astra`，推理 `max`，Standard 处理 |
| 结构 | 18 个节点、19 条连接，与论文方法核对 |
| 图片 | `gpt-image-2.5-sunburst`，画质 `max`，3840 × 2160 |
| 渲染 | Pastel、ML TopConf Deep 配色、文生图 |
| 精修 | 两次 Image API 编辑，第二次使用编辑蒙版 |
| 最终排版 | 本地 5:2 构图，4800 × 1920，不再调用生图接口 |

[manifest.json](mae/manifest.json) 记录实际耗时、Token 用量和提示词修订版本。后端在审阅后的绘图提示词末尾附加风格方向和语义配色，再调用 Image API。

## 文件

| 文件 | 内容 |
| --- | --- |
| [method-notes.txt](mae/method-notes.txt) | 动图使用的简短方法概要 |
| [request.json](mae/request.json) | 本次实际配图需求 |
| [prompt.txt](mae/prompt.txt) | 审阅后的英文绘图提示词 |
| [image-prompt.txt](mae/image-prompt.txt) | 实际发送给 Image API 的完整提示词 |
| [edit-prompt.txt](mae/edit-prompt.txt) | 参考图精修使用的完整提示词 |
| [connector-prompt.txt](mae/connector-prompt.txt) | 蒙版编辑使用的完整提示词 |
| [refined.png](mae/refined.png)、[repair-base.png](mae/repair-base.png) | 用于排版的 Image API 编辑输出 |
| [layout_mae.py](../../docs/demo/layout_mae.py) | 可复现的横向排版与端点连线脚本 |
| [figure-spec.json](mae/figure-spec.json) | 语义结构，公开副本省略论文逐字引文 |
| [manifest.json](mae/manifest.json) | 论文出处、章节对应关系、实际设置、耗时和用量 |
| [visual-contract.md](mae/visual-contract.md) | 科学结构与构图决策 |
| [figure.png](mae/figure.png) | 4800 × 1920 最终 PNG |

上传的 PDF 和精确原文引用保留在本地工作台。公开 FigureSpec 是语义结构，并非 PNG 的矢量重建版本。

动图源码与构建方式：[docs/demo](../../docs/demo/README.md)。
