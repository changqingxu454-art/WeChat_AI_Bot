import requests
import json
import csv
import os
import schedule
import time
from wxauto import WeChat


class WeChatBot:
    def __init__(self):
        self.wx = WeChat()
        self.list_name = [
            '徐长卿',  # 机器人账号添加管理员的备注，徐长卿为管理员，ros为机器人，ros给管理员的备注就应为徐长卿，可进行修改
            '嘻嘻嘻',  # 被监控群聊名称
            'AAA刘哥百货超市',
            '小超市'
        ]
        # 为每个群聊添加监听
        for group in self.list_name:
            self.wx.AddListenChat(who=group, savepic=True)


    def call_ai_model(self, content):
        """调用百度千帆新版大模型（v2接口）"""
        API_KEY = "自行获取"
        url = "自行获取"

        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }

        data = {
            "model": "ernie-3.5-8k",
            "messages": [{"role": "user", "content": content}]
        }

        try:
            response = requests.post(url, headers=headers, data=json.dumps(data), timeout=10)
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
            else:
                print("AI调用失败：", response.text)
                return None
        except Exception as e:
            print("AI请求异常：", e)
            return None

    def send_morning_wishes(self):
        """发送早安祝福消息"""
        good_morning_message = "老板生成一段祝福群友的早安祝福"
        ai_reply = self.call_ai_model(good_morning_message)
        if ai_reply:
            for group in self.list_name:
                self.wx.SendMsg(msg=ai_reply, who=group)

    def send_evening_greetings(self):
        """发送晚上好的消息"""
        evening_greetings = "老板生成一段祝福群友的晚上好祝福"
        ai_reply = self.call_ai_model(evening_greetings)
        if ai_reply:
            for group in self.list_name:
                self.wx.SendMsg(msg=ai_reply, who=group)

    def listen_messages(self):
        # 持续监听消息
        wait = 1  # 设置1秒查看一次是否有新消息
        while True:
            msgs = self.wx.GetListenMessage()
            for chat, messages in msgs.items():
                # 获取聊天窗口名（群名）
                who = chat.who
                # 检查是否是指定的群聊
                if who in self.list_name:
                    for msg in messages:
                        msg_type = msg.type  # 获取消息类型
                        content = msg.content  # 获取消息内容
                        print(f'【{who}】：{content}')
                        # 获取发送者信息
                        sender = msg.sender
                        # 根据群聊名称和消息内容回复不同的消息
                        if who != self.list_name[0]:
                            if content.startswith('购买'):
                                try:
                                    parts = content.split('购买')[1].strip()
                                    commodity_name, quantity = parts.split(' ', 1)
                                    if self.is_commodity_exists(commodity_name):
                                        reply = f"{sender}，已为您将{commodity_name}{quantity}添加至订单中，感谢您的支持"
                                        self.save_to_csv_order(sender, commodity_name, quantity)
                                        self.wx.SendMsg(msg=reply, who=who)
                                    else:
                                        reply = f"{sender}，该商品小店尚未出售"
                                        self.wx.SendMsg(msg=reply, who=who)
                                except ValueError:
                                    reply = f"{sender}，输入格式错误，请按照'购买 商品名称 购买数量'的格式输入。"
                                    self.wx.SendMsg(msg=reply, who=who)
                            elif content.startswith('查询'):
                                parts = content.split('查询')[1].strip()
                                if parts:  # 确保有商品信息
                                    commodity_name = parts
                                    if self.is_commodity_exists(commodity_name):
                                        price_info = self.get_price_info(commodity_name)
                                        reply = f"{sender}，{commodity_name} {price_info}"
                                    else:
                                        reply = f"{sender}，该商品小店尚未出售"
                                    self.wx.SendMsg(msg=reply, who=who)
                            if content.startswith('老板'):
                                ai_reply = self.call_ai_model(content[2:])
                                if ai_reply:
                                    self.wx.SendMsg(msg=ai_reply, who=who)
                        elif who == self.list_name[0]:
                            if content.startswith('转发'):
                                # 转发消息到其他所有监控群聊，删除“转发”二字
                                new_content = content[2:].strip()
                                self.forward_message(new_content)
                            if content.startswith('增加'):
                                try:
                                    parts = content.split('增加')[1].strip()
                                    if parts:  # 确保有商品信息
                                        commodity_name, price_info = parts.split(' ', 1)
                                        if self.is_commodity_exists(commodity_name):
                                            reply = f"{sender}，{commodity_name}已经存在。"
                                        else:
                                            reply = f"{sender}，{commodity_name}增加成功。"
                                            self.save_to_csv(commodity_name, price_info)
                                        self.wx.SendMsg(msg=reply, who=who)
                                except ValueError:
                                    reply = f"{sender}，输入格式错误，请按照'增加 商品名称 价格信息'的格式输入。"
                                    self.wx.SendMsg(msg=reply, who=who)
                            elif content.startswith('删除'):
                                commodity_name = content.split('删除')[1].strip()
                                if self.delete_commodity_from_csv(commodity_name):
                                    reply = f"{sender}，{commodity_name}删除成功。"
                                else:
                                    reply = f"{sender}，{commodity_name}不存在。"
                                self.wx.SendMsg(msg=reply, who=who)
            schedule.run_pending()
            time.sleep(wait)

    def forward_message(self, content):
        """将消息转发到所有监控的群聊"""
        for group in self.list_name:
            if group != self.list_name[0]:  # 排除发送“转发”命令的群聊
                self.wx.SendMsg(msg=content, who=group)

    def save_to_csv_order(self, username, commodity_name, quantity):
        # 将订单信息保存到order.csv中
        with open('order.csv', 'a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            # 写入用户名、商品名称和数量
            writer.writerow([username, commodity_name, quantity])
        print(f"订单 '{commodity_name}' 已添加到order.csv")

    def get_price_info(self, commodity_name):
        # 从commodity.csv中获取商品的价格信息
        with open('commodity.csv', 'r', newline='', encoding='utf-8') as file:
            reader = csv.reader(file)
            for row in reader:
                if row and row[0] == commodity_name:
                    return row[1]
        return "未知价格"

    def save_to_csv(self, commodity_name, price_info):
        # 将信息保存到commodity.csv中
        with open('commodity.csv', 'a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            # 写入商品名称和价格信息
            writer.writerow([commodity_name, price_info])
        print(f"商品 '{commodity_name}' 已添加到commodity.csv")

    def is_commodity_exists(self, commodity_name):
        # 检查商品是否存在
        if not os.path.exists('commodity.csv'):
            return False
        with open('commodity.csv', 'r', newline='', encoding='utf-8') as file:
            reader = csv.reader(file)
            for row in reader:
                if row and row[0] == commodity_name:
                    return True
        return False

    def delete_commodity_from_csv(self, commodity_name):
        # 删除CSV文件中的商品
        lines = []
        found = False
        with open('commodity.csv', 'r', newline='', encoding='utf-8') as file:
            reader = csv.reader(file)
            for row in reader:
                if row and row[0] != commodity_name:
                    lines.append(row)
                elif row:
                    found = True
        with open('commodity.csv', 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerows(lines)
        return found

    def start(self):
        schedule.every().day.at("08:30").do(self.send_morning_wishes)
        schedule.every().day.at("19:30").do(self.send_evening_greetings)

        # 开始监听消息
        self.listen_messages()


if __name__ == "__main__":
    bot = WeChatBot()
    bot.start()
