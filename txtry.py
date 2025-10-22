import requests
import json
import json
from typing import List, Dict, Union
import re
import ast
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import calendar
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from tencentcloud import sse_client

def clean_str(input_str):
    """
    清理时间线字符串并处理成结构化数据
    
    参数:
        input_str: 输入的时间线字符串，可能包含转义字符和引用标记
        
    返回:
        处理后的字典列表，每个字典包含time, event和refer字段
    """
    # 1. 去除所有反斜杠
    cleaned_str = input_str.replace('\\', '')
    cleaned_str = cleaned_str.replace('```', '')
    cleaned_str = cleaned_str.replace('python', '')
    cleaned_str = cleaned_str.replace(' ', '')
    cleaned_str = "".join(cleaned_str.split())
    compressed = cleaned_str
    
    # 查找第一个 [{ 和最后一个 }]
    start = compressed.find('[{')
    end = compressed.rfind('}]')
    
    # 检查是否找到匹配
    if start != -1 and end != -1 and start < end:
        cleaned_str= compressed[start:end+2]  # +2 包含 }] 的两个字符

    try:
        # 先尝试用json解析（更安全）
        data = json.loads(cleaned_str)
    except json.JSONDecodeError:
        try:
            # 如果json解析失败，尝试用ast安全解析
            import ast
            data = ast.literal_eval(cleaned_str)
        except (SyntaxError, ValueError) as e:
            raise ValueError(f"字符串解析失败: {e}")
    
    if not isinstance(data, list):
        raise ValueError("输入数据不是有效的列表格式")
    
    processed_list = []
    for item in data:
        if not isinstance(item, dict):
            continue
            
        time = str(item.get('time', ''))
        event = str(item.get('event', ''))
        sum = str(item.get('sum', ''))
        
        # 3. 处理引用标记
        refer_ids = []
        
        # 匹配所有^^之间的内容
        ref_markers = re.findall(r'\^(.*?)\^', event)
        for marker in ref_markers:
            # 匹配[]中的数字
            ids_in_marker = re.findall(r'\[(\d+)\]', marker)
            for id_str in ids_in_marker:
                try:
                    refer_ids.append(int(id_str))
                except ValueError:
                    continue
        
        # 去除所有引用标记（^^之间的所有内容）
        cleaned_event = re.sub(r'\^.*?\^', '', event).strip()
        
        # 4. 创建新字典并添加refer字段
        processed_list.append({
            'time': time,
            'event': cleaned_event,
            'sum' : sum,
            'refer': list(sorted(set(refer_ids)))  # 去重并排序
        })
    
    return processed_list



def generate_search_terms(topic, start_date, end_date):
    """
    生成时间范围内的搜索词列表
    
    参数:
        topic: 主题词
        start_date: 开始年月 (格式: "YYYY-MM")
        end_date: 结束年月 (格式: "YYYY-MM")
        
    返回:
        包含年月和主题的搜索词列表
    """
    if start_date ==-1:
        return [f"{topic} 详细时间脉络事件发展"]
    try:
        # 解析输入日期
        start = datetime.strptime(start_date, "%Y-%m")
        end = datetime.strptime(end_date, "%Y-%m")
        
        # 确保开始日期不晚于结束日期
        if start > end:
            start, end = end, start
        
        search_terms = []
        current = start
        
        # 生成每个月的时间脉络
        while current <= end:
            # 获取该月的第一天和最后一天
            first_day = current.replace(day=1)
            last_day = current.replace(day=calendar.monthrange(current.year, current.month)[1])
            
            # 生成时间脉络描述
            time_period = f"{current.strftime('%Y年%m月')}"
            
            # 创建搜索词
            search_term = f"{time_period}{topic}详细完整脉络,你要严格按照时间主题输出"
            #search_term = f"{time_period}{topic}事件集合,你要严格按照时间主题输出"
            search_terms.append(search_term)
            
            # 移动到下个月
            current += relativedelta(months=+1)
        
        return search_terms
    
    except ValueError as e:
        raise ValueError(f"日期格式错误，请使用'YYYY-MM'格式: {e}")

def tencentcloudbytime(content):
    rawrefer, rawresult = sse_client(content)
    print(rawresult)
    #print((rawresult)["payload"]['content'])
    timeline = clean_str((rawresult))
    refernce = (rawrefer)['payload']['references']
    for refer in refernce:
        refer['id'] = int(refer['id'])
    #print(response.text)
    return timeline, refernce

def extract_and_filter(timeline_str, dict_list):
    """
    1. 从字符串前8个字符提取年月（格式：yyyy年mm月）
    2. 筛选字典列表，保留time字段符合该年月的字典
    
    参数:
        timeline_str: 时间线字符串
        dict_list: 包含time字段的字典列表
        
    返回:
        tuple: (提取的年月字符串, 筛选后的字典列表)
    """
    # 1. 提取前8个字符并检查格式
    prefix = timeline_str[:8]
    try:
        # 尝试解析为年月格式
        year_month = datetime.strptime(prefix, "%Y年%m月").strftime("%Y-%m")
    except ValueError:
        # 格式不匹配则返回空和原列表
        return "", dict_list
    
    # 2. 筛选字典列表
    filtered_list = []
    for item in dict_list:
        if not isinstance(item, dict):
            continue
        
        time_str = item.get('time', '')
        try:
            # 检查time字段是否以目标年月开头
            if time_str.startswith(year_month):
                filtered_list.append(item)
        except AttributeError:
            continue
    
    return f"{prefix}", filtered_list


def tlsByQianFan(topic, start, end,web_filter):
    querylist = generate_search_terms(topic, start, end)
    tllist = []
    referlist = []

    def process_query(idx, query):
        """并发执行的任务函数"""
        offset = 0  # offset 需后面统一计算
        for retry in range(5):
            try:
            #if 1:
                #timeline, reference = qianfanbytime(query,web_filter)
                timeline, reference = tencentcloudbytime(query)
                #print('over')
                _, timeline = extract_and_filter(query, timeline)
                #print("end")
                return idx, query, timeline, reference
            except Exception as e:
                print(f"erro ({query}): {e}")
            time.sleep(2)
        return idx, query, [], []

    # === 并发执行 ===
    results = []
    with ThreadPoolExecutor(max_workers=5) as executor:  # 可调线程数
        futures = [executor.submit(process_query, i, q) for i, q in enumerate(querylist)]
        for f in tqdm(as_completed(futures), total=len(futures)):
            results.append(f.result())

    # === 按原始顺序恢复 ===
    results.sort(key=lambda x: x[0])  # 保持 querylist 顺序

    # === 合并结果 ===
    for _, query, timeline, reference in results:
        offset = len(referlist)
        query_time = query[:8]
        for tl in timeline:
            tl['refer'] = [ref + offset for ref in tl['refer']]
            tllist.append(tl)
        for rf in reference:
            rf["id"] = rf["id"] + offset
            referlist.append(rf)

    return tllist, referlist


def save_list_to_json(data_list: list, file_path: str) -> None:
    """
    将列表保存为 JSON 文件
    
    参数:
        data_list: 要保存的列表
        file_path: 保存的文件路径（如 'data.json'）
    """
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data_list, f, ensure_ascii=False, indent=4)
    
def main():
    topic = "中菲南海冲突"
    start ="2012-01"
    end = "2025-10"
    web_filter = []#['news.cctv.cn','mfa.gov.cn','fmprc.gov.cn',"news.cn",'paper.people.com.cn','ccg.gov.cn','politics.people.com.cn','mod.gov.cn']
    tl,refer = tlsByQianFan(topic,start,end,web_filter)
    save_list_to_json(tl,"tx-sum.json")
    save_list_to_json(refer,"referencetx-sum.json")
    

if __name__ == '__main__':
    main()
