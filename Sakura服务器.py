import os
import re
import json
from flask import Flask, request  #需要安装库 pip install Flask
from gevent.pywsgi import WSGIServer  #需要安装库 pip install gevent
from urllib.parse import unquote
from threading import Thread
from queue import Queue

from openai import OpenAI   #需要安装库 pip install openai


dict_path='用户提示字典.json' # 提示字典路径，不使用则留空

# API配置
Base_url = "http://127.0.0.1:8080"    #获取请求地址
Model_Type =  "Sakura-13B-LNovel-v0.9"    #获取模型类型 Sakura-13B-LNovel-v0.8或者Sakura-13B-LNovel-v0.9
Proxy_port = ''  # 代理端口，如果不使用代理则为空

# 中文字符不足1/n时，换下一个提示词重新翻译
n=3
# 结果中有任意短语或单字连续出现大于等于repeat_count次并且原文中没有连续出现repeat_count-2次的短语，换下一提示词重新翻译
repeat_count=3
# 提示词，按照使用顺序添加进prompt_ist
prompt= '你是一个轻小说翻译模型，可以流畅通顺地以日本轻小说的风格将日文翻译成简体中文，并联系上下文正确使用人称代词，不擅自添加原文中没有的代词。'

prompt_list=[prompt]
l=len(prompt_list)
# 提示字典的提示词,最终的提示词是prompt+dprompt+提示字典，不使用提示字典可以不管
dprompt0='\n在翻译中使用以下字典,字典的格式为{\'原文\':\'译文\'}\n'
dprompt1='\nDuring the translation, use a dictionary in {\'Japanese text \':\'translated text \'} format\n'
# list，长度应该和提示词list相同，二者同步切换
dprompt_list=[dprompt0,dprompt1,dprompt1]

app = Flask(__name__)

# 如果填入代理端口，则设置系统代理
if Proxy_port:
    os.environ["http_proxy"] = Proxy_port
    os.environ["https_proxy"] = Proxy_port

#检查一下请求地址尾部是否为/v1，自动补全
if Base_url[-3:] != "/v1":
    Base_url = Base_url + "/v1"

# 创建openai客户端
openai_client = OpenAI(api_key="sakura", base_url= Base_url)

# 读取提示字典,并从长倒短排序
if dict_path:
    with open(dict_path, 'r', encoding='utf8') as f:
        tempdict = json.load(f)
    sortedkey = sorted(tempdict.keys(), key=lambda x: len(x), reverse=True)
    prompt_dict = {}
    for i in sortedkey:
        prompt_dict[i] = tempdict[i]
else:
    prompt_dict= {}

# 判断中文字符(包括标点）长度是否不足总字符串长度的1/n
def is_chinese_text_shorter_than(text):
    pattern = re.compile(r'[!.,?，。？\u4e00-\u9fff\u3000-\u303f\uff01-\uffef0-9]+')
    chars = pattern.findall(text)
    char_count = sum(len(char) for char in chars)
    return char_count < len(text) / n

# 检测是否有任一短语连续出现超过count+1次,检测范围除外了中日标点和!.,?，。？
def has_repeated_sequence(string,count):
    pattern = re.compile(fr"([^!.,?，。？\u3000-\u303F\uFF00-\uFFEF]+?)\1{{{count-1}}}")
    match = re.search(pattern, string)
    return bool(match)

# 获得文本中包含的字典词汇
def get_dict(text):
    res={}
    for key in prompt_dict.keys():
        if key in text:
            res.update({key:prompt_dict[key]})
            text=text.replace(key,'')   # 从长倒短查找文本中含有的字典原文，找到后就删除它，避免出现长字典包含短字典的情况
        if text=='':
            break
    return res


def handle_translation(text, queue):
    # 对接收到的文本进行URL解码
    text = unquote(text)
    
    # 定义特殊字符
    special_chars = ['，', '。', '？','...']

    # 记录文本末尾是否有特殊字符，并存储该字符
    text_end_special_char = None
    if text[-1] in special_chars:
        text_end_special_char = text[-1]   

    # 检测文本中是否包含特殊字符，并记录
    special_char_start = "「"
    special_char_end = "」"
    has_special_start = text.startswith(special_char_start)
    has_special_end = text.endswith(special_char_end)
    
    # 如果文本同时包含开始和结束的特殊字符，则在翻译前移除它们
    if has_special_start and has_special_end:
        text = text[len(special_char_start):-len(special_char_end)]        

    # 更多模型参数
    model_params = {
        "temperature": 0.1, 
        "frequency_penalty": 0.1,
        "max_tokens": 1000, 
        "top_p": 0.3, 
    }
    try:
        dict_inuse=get_dict(text)
        # 对提示词列表遍历，有任意一次结果符合要求，break
        for i in range(0,l):
            prompt=prompt_list[i]
            if dict_inuse:
                prompt+=dprompt_list[i]+str(dict_inuse)
            # 构建API请求数据
            messages_test = [
                {"role": "system", "content": prompt},
                {"role": "user", "content": text}
            ]
            # 发送API请求，并获取翻译结果
            response_test = openai_client.chat.completions.create(
                model=Model_Type,
                messages=messages_test,
                **model_params  # 添加更多模型参数
            )
            # 提取翻译文本
            translations = response_test.choices[0].message.content
            print(f'{prompt}\n{translations}')

            # 如果原文本包含特殊字符，将翻译结果包裹起来
            if has_special_start and has_special_end:
                if not translations.startswith(special_char_start):
                    translations = special_char_start + translations
                if not translations.endswith(special_char_end):
                    translations = translations + special_char_end
                elif has_special_start and not translations.startswith(special_char_start):
                    translations = special_char_start + translations
                elif has_special_end and not translations.endswith(special_char_end):
                    translations = translations + special_char_end
                    
            # 检查翻译结果是否以特殊字符结束
            translation_end_special_char = None
            if translations[-1] in special_chars:
                translation_end_special_char = translations[-1]
                
            # 如果接收的文本和翻译结果的末尾特殊字符不匹配，则进行更正
            if text_end_special_char and translation_end_special_char:
                if text_end_special_char != translation_end_special_char:
                    translations = translations[:-1] + text_end_special_char
            elif text_end_special_char and not translation_end_special_char:
                translations += text_end_special_char
            elif not text_end_special_char and translation_end_special_char:
                translations = translations[:-1]
                
              
            repeat_check=has_repeated_sequence(translations,repeat_count)

            
            if not is_chinese_text_shorter_than(translations) and not repeat_check:
                break
            # 如果结果含重复短语，增加重复惩罚
            if repeat_check:
                model_params['frequency_penalty']+=1/l

        # 打印翻译结果
        print(f"翻译结果: {translations}")
        queue.put(translations)

    except Exception as e:
        print(f"请求出现问题！错误信息如下: {e}")
        queue.put(False)

# 定义处理翻译的路由
@app.route('/translate', methods=['GET'])  
def translate():
    # 从GET请求中获取待翻译的文本
    text = request.args.get('text')  
    print(f"接收到的文本: {text}")

    translation_queue = Queue()
    translation_thread = Thread(target=handle_translation, args=(text, translation_queue))
    translation_thread.start()
    translation_thread.join()

    translation = translation_queue.get()

    if translation:
         return f"{translation}"
    else:
         return "翻译失败", 500

def main():
    print("服务器在 http://127.0.0.1:4000 上启动")
    http_server = WSGIServer(('127.0.0.1', 4000), app, log=None, error_log=None)
    http_server.serve_forever()

if __name__ == '__main__':
    main()
