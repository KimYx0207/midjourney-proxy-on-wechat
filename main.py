# encoding:utf-8
import time
import requests
import os
import json
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger
import plugins
from plugins import *

def check_prefix(content, prefix_list):
    prefix_list = eval(prefix_list)
    if not prefix_list:
        return False, None
    for prefix in prefix_list:
        logger.info("[MJ] prefix={} content={} test={}".format(prefix, content, content.startswith(prefix)))
        if content.startswith(prefix):
            return True, content.replace(prefix, "").strip()
    return False, None

@plugins.register(
    name="MidJourney",
    desc="一款AI绘画工具",
    version="1.0.8",
    author="mouxan"
)
class MidJourney(Plugin):
    def __init__(self):
        super().__init__()
        self.mj_url = os.environ.get("mj_url", None)
        self.mj_api_secret = os.environ.get("mj_api_secret", None)
        self.imagine_prefix = os.environ.get("imagine_prefix", "[\"/imagine\", \"/mj\", \"/img\"]")
        self.fetch_prefix = os.environ.get("fetch_prefix", "[\"/fetch\", \"/ft\"]")
        try:
            if not self.mj_url or not self.mj_api_secret:
                curdir = os.path.dirname(__file__)
                config_path = os.path.join(curdir, "config.json")
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    if not self.mj_url:
                        self.mj_url = config["mj_url"]
                    if self.mj_url and not self.mj_api_secret:
                        self.mj_api_secret = config["mj_api_secret"]
            self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
            logger.info("[MJ] inited. mj_url={} mj_api_secret={} help_prefix={} imagine_prefix={}".format(self.mj_url, self.mj_api_secret, self.help_prefix, self.imagine_prefix))
        except Exception as e:
            if isinstance(e, FileNotFoundError):
                logger.warn(f"[MJ] init failed, config.json not found.")
            else:
                logger.warn("[MJ] init failed." + str(e))
            raise e

    def on_handle_context(self, e_context: EventContext):
        if e_context["context"].type not in [
            ContextType.TEXT,
        ]:
            return
        
        mj = _mjApi(self.mj_url, self.mj_api_secret)

        channel = e_context['channel']
        context = e_context['context']
        content = context.content

        if content == "/mjhp" or content == "/mjhelp" or content == "/mj-help":
            reply = Reply(ReplyType.INFO, mj.help_text())
            e_context["reply"] = reply
            e_context.action = EventAction.BREAK_PASS  # 事件结束，并跳过处理context的默认逻辑
            return
        
        iprefix, iq = check_prefix(content, self.imagine_prefix)
        if iprefix == True or content.startswith("/up"):
            logger.info("[MJ] iprefix={} iq={}".format(iprefix,iq))
            reply = None
            if iprefix == True:
                status, msg, id = mj.imagine(iq)
            else:
                status, msg, id = mj.simpleChange(content.replace("/up", "").strip())
            if status:
                self.sendMsg(channel, context, ReplyType.TEXT, msg)
                status2, msgs, imageUrl = mj.get_f_img(id)
                if status2:
                    self.sendMsg(channel, context, ReplyType.TEXT, msgs)
                    reply = Reply(ReplyType.IMAGE_URL, imageUrl)
                else:
                    reply = Reply(ReplyType.ERROR, msgs)
            else:
                reply = Reply(ReplyType.ERROR, msg)
            e_context["reply"] = reply
            e_context.action = EventAction.BREAK_PASS
            return
        
        fprefix, fq = check_prefix(content, self.fetch_prefix)
        if fprefix == True:
            logger.info("[MJ] fprefix={} fq={}".format(fprefix,fq))
            status, msg, imageUrl = mj.fetch(fq)
            reply = None
            if status:
                self.sendMsg(channel, context, ReplyType.TEXT, msg)
                if imageUrl:
                    reply = Reply(ReplyType.IMAGE_URL, imageUrl)
            else:
                reply = Reply(ReplyType.ERROR, msg)
            e_context["reply"] = reply
            e_context.action = EventAction.BREAK_PASS
            return


    def get_help_text(self, isadmin=False, isgroup=False, verbose=False,**kwargs):
        if kwargs.get("verbose") != True:
            return "这是一个AI绘画工具，只要输入想到的文字，通过人工智能产出相对应的图。"
        else:
            return _mjApi().help_text()
    
    def sendMsg(self, channel, context, types, msg):
        return channel._send_reply(context, channel._decorate_reply(context, Reply(types, msg)))



class _mjApi:
    def __init__(self, mj_url, mj_api_secret):
        self.baseUrl = mj_url
        self.headers = {
            "Content-Type": "application/json",
        }
        if mj_api_secret:
            self.headers["mj-api-secret"] = mj_api_secret
    
    def imagine(self, text):
        try:
            url = self.baseUrl + "/mj/submit/imagine"
            data = {"prompt": text}
            res = requests.post(url, json=data, headers=self.headers)
            code = res.json()["code"]
            if code == 1:
                msg = "✅ 您的任务已提交\n"
                msg += f"🚀 正在快速处理中，请稍后\n"
                msg += f"📨 任务ID: {res.json()['result']}\n"
                msg += f"🪄 查询进度\n"
                msg += f"✏  使用[/fetch + 任务ID操作]\n"
                msg += f"/fetch {res.json()['result']}"
                return True, msg, res.json()["result"]
            else:
                return False, res.json()["description"]
        except Exception as e:
            return False, "图片生成失败"
    
    def simpleChange(self, content):
        try:
            url = self.baseUrl + "/mj/submit/simple-change"
            data = {"content": content}
            res = requests.post(url, json=data, headers=self.headers)
            code = res.json()["code"]
            if code == 1:
                msg = "✅ 您的任务已提交\n"
                msg += f"🚀 正在快速处理中，请稍后\n"
                msg += f"📨 任务ID: {res.json()['result']}\n"
                msg += f"🪄 查询进度\n"
                msg += f"✏  使用[/fetch + 任务ID操作]\n"
                msg += f"/fetch {res.json()['result']}"
                return True, msg, res.json()["result"]
            else:
                return False, res.json()["description"]
        except Exception as e:
            return False, "图片生成失败"
    
    def fetch(self, id):
        try:
            url = self.baseUrl + f"/mj/task/{id}/fetch"
            res = requests.get(url, headers=self.headers)
            status = res.json()['status']
            startTime = ""
            finishTime = ""
            if res.json()['startTime']:
                startTime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(res.json()['startTime']/1000))
            if res.json()['finishTime']:
                finishTime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(res.json()['finishTime']/1000))
            msg = "✅ 查询成功\n"
            msg += f"任务ID: {res.json()['id']}\n"
            msg += f"描述内容：{res.json()['prompt']}\n"
            msg += f"状态：{self.status(status)}\n"
            msg += f"进度：{res.json()['progress']}\n"
            if startTime:
                msg += f"开始时间：{startTime}\n"
            if finishTime:
                msg += f"完成时间：{finishTime}\n"
            if res.json()['imageUrl']:
                return True, msg, res.json()['imageUrl']
            return True, msg, None
        except Exception as e:
            return False, "查询失败"
    
    def status(self, status):
        msg = ""
        if status == "SUCCESS":
            msg = "已成功"
        elif status == "FAILURE":
            msg = "失败"
        elif status == "SUBMITTED":
            msg = "已提交"
        elif status == "IN_PROGRESS":
            msg = "处理中"
        else:
            msg = "未知"
        return msg
    
    def get_f_img(self, id):
        try:
          url = self.baseUrl + f"/mj/task/{id}/fetch"
          status = ""
          rj = ""
          while status != "SUCCESS":
              time.sleep(3)
              res = requests.get(url, headers=self.headers)
              rj = res.json()
              status = rj["status"]
          action = rj["action"]
          msg = ""
          if action == "IMAGINE":
              msg = f"🎨 绘图成功\n"
              msg += f"✨ 内容: {rj['prompt']}\n"
              msg += f"✨ 内容: {rj['prompt']}\n"
              msg += f"📨 任务ID: {id}\n"
              msg += f"🪄 放大 U1～U4，变换 V1～V4\n"
              msg += f"✏ 使用[/up 任务ID 操作]\n"
              msg += f"/up {id} U1"
          elif action == "UPSCALE":
              msg = "🎨 放大成功\n"
              msg += f"✨ {rj['description']}\n"
          return True, msg, rj["imageUrl"]
        except Exception as e:
            return False, "绘图失败"
    
    def help_text(self):
        help_text = "欢迎使用MJ机器人\n"
        help_text += f"这是一个AI绘画工具，只要输入想到的文字，通过人工智能产出相对应的图。\n"
        help_text += f"------------------------------\n"
        help_text += f"🎨 AI绘图-使用说明：\n"
        help_text += f"输入: /mj prompt\n"
        help_text += f"prompt 即你提的绘画需求\n"
        help_text += f"------------------------------\n"
        help_text += f"📕 prompt附加参数 \n"
        help_text += f"1.解释: 在prompt后携带的参数, 可以使你的绘画更别具一格\n"
        help_text += f"2.示例: /mj prompt --ar 16:9\n"
        help_text += f"3.使用: 需要使用--key value, key和value空格隔开, 多个附加参数空格隔开\n"
        help_text += f"------------------------------\n"
        help_text += f"📗 附加参数列表\n"
        help_text += f"1. --v 版本 1,2,3,4,5 默认5, 不可与niji同用\n"
        help_text += f"2. --niji 卡通版本 空或5 默认空, 不可与v同用\n"
        help_text += f"3. --ar 横纵比 n:n 默认1:1\n"
        help_text += f"4. --q 清晰度 .25 .5 1 2 分别代表: 一般,清晰,高清,超高清,默认1\n"
        help_text += f"5. --style 风格 (4a,4b,4c)v4可用 (expressive,cute)niji5可用\n"
        help_text += f"6. --s 风格化 1-1000 (625-60000)v3"
        return help_text