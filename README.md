# XUnity.AutoTranslator-Sakura
# 介绍
基于XUnity.AutoTranslator和Sakura模型的Unity游戏本地翻译器  
# 准备
Sakura模型本地部署[Sakura模型本地部署教程](https://github.com/SakuraLLM/Sakura-13B-Galgame/wiki/llama.cpp%E4%B8%80%E9%94%AE%E5%8C%85%E9%83%A8%E7%BD%B2%E6%95%99%E7%A8%8B)  
建议使用Sakura v0.9b模型[Sakura v0.9b](https://huggingface.co/SakuraLLM/Sakura-13B-LNovel-v0.9b-GGUF/tree/main) 
# 流程
确保Sakura服务器成功启动并监听(http://127.0.0.1:8080)

更改XUnity.AutoTranslator插件的AutoTranslatorConfig.ini或者Config.ini文件  

[Service]  
Endpoint=CustomTranslate  
[Custom]  
Url=http://127.0.0.1:4000/translate  
