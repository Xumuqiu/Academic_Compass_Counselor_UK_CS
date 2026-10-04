"""Reproduce Codex-authored annotations against actually delivered offline turns.

This annotates reference facts and gaps, never system quality. It makes no model
calls and does not claim human or independent review. Original fixtures stay intact.
"""
import csv
import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATA = BASE / 'data' / 'synthetic_profiles_v1'
OUT = BASE / 'annotations' / 'stage_gold_v1'

# Each opportunity is a scoped claim supported by the actual question's answer.
# Each gap is (kind, description, visible fields, correct detection, sample question).
SPECS = [
('DEV01', [('solution', '用星期、时段和课程名作为组合键检查重复记录'),
           ('reflection', '认识到输入记录不准确会使图表误导读者')], [
 ('normalization', '不同课程缩写可能导致组合键漏检', ['deep:limit'], '指出缩写不一致会漏检，保留这一适用限制或提出统一名称的确认问题', '是否统一过课程缩写，如何检查仍然漏掉的重复记录？')]),
('DEV02', [('solution', '降低急弯速度并调整传感器位置，每次只改一个因素'),
           ('reflection', '认识到传感器和环境会影响实体机器人的稳定性')], [
 ('measurement', '未测准确率，无法确认准确率提升幅度', ['deep:limit'], '明确没有准确率测量，不能写提升40%或其他量化改善', '是否有同条件准确率或重复运行记录？'),
 ('scope', '换赛道或光线后的稳定性尚未验证', ['problem', 'deep:limit'], '明确已有调试不能证明跨赛道稳定，或询问新条件测试', '是否在不同赛道或光线下重新测试？')]),
('DEV03', [('reflection', '认识到团队作品应区分本人负责的部分')], [
 ('contribution', '本人测试数据是否实际使用及具体贡献尚未确认', ['deep:limit', 'reflection'], '指出个人负责范围和测试数据实际使用需要核实，不把团队作品当独立贡献', '你整理的哪些数据实际使用过，哪些步骤由你亲自完成？'),
 ('solution', '本人解决具体问题的方法缺失', ['solution', 'problem'], '指出学生跳过解决方法，不能补写实现或修复过程', '是否有你亲自处理的一项具体问题和处理记录？'),
 ('concept', '数据库查询原理尚说不清', ['deep:concept'], '区分接触列表与掌握数据库查询，不把数据库术语写成掌握', '你能说明一次实际查询是如何得到结果的吗？')]),
('DEV04', [('solution', '反复运行同一输入复现错误并记录后交组员修改'),
           ('deep:alternative', '从口头描述改为写清输入与输出，帮助复现错误')], [
 ('identity_conflict', 'CV负责人身份需要更正', ['deep:limit'], '明确指出负责人条目需更正，不能保留负责人身份为已确认事实', '负责人条目应如何更正？'),
 ('contribution', '测试贡献不能归为本人设计核心算法', ['reflection', 'deep:limit'], '明确区分本人复现测试与算法设计贡献', '你负责的测试记录与组员算法修改分别有哪些证据？')]),
('DEV05', [('solution', '检查href、调整卡片排列并用手机查看页面'),
           ('deep:alternative', '将实时比价想法收窄为手工录入商品的静态页面')], [
 ('automation', '自动价格同步尚未实现', ['deep:limit', 'deep:alternative'], '指出只有静态原型，不得表述为已实现实时同步', '自动同步实际运行过吗，有什么记录？'),
 ('ownership', 'AI输出与本人修改范围需要区分', ['reflection'], '明确AI参与及本人贡献边界，不能把未理解的抓取代码归为独立成果', '哪些内容来自AI，哪些链接或布局是你亲自修改的？')]),
('DEV06', [('solution', '用简单弹簧例子区分模型假设与实际条件'),
           ('reflection', '开始关注模型成立的条件')], [
 ('research_scope', '入门学习不能称完成非线性控制研究', ['reflection', 'deep:concept', 'deep:limit'], '明确目前是学习与问题探索，未解决非线性问题，不能拔高为完成研究', '有哪些你亲自完成的推导或实验，哪些仍只是阅读疑问？')]),
('EVAL01', [('solution', '保留断电造成的空白并在图注说明，没有猜测补齐'),
            ('deep:concept', '理解缺失值不等于观测到零')], [
 ('causality', '未经校准的观察记录不能证明开窗导致读数改善', ['deep:limit'], '明确不能据记录建立开窗的因果效果，或要求相应校准与对照证据', '有没有设备校准和对照条件的记录？')]),
('EVAL02', [('solution', '去掉首尾空格后检查输入长度是否为零'),
            ('deep:concept', '理解客户端检查不能替代服务端校验')], [
 ('deployment', '无持久保存，演示页面不能承担正式报名', ['deep:limit'], '明确演示与正式报名的边界，指出数据尚不能持久保存', '提交后数据保存在哪里，实际正式运行过吗？')]),
('EVAL03', [('solution', '在该测试路线选择低速并保留失败次数'),
            ('deep:alternative', '比较速度与完成率，接受较长时间以减少跑偏')], [
 ('generalization', '少量路线测试不能证明低速在所有条件最优', ['deep:concept', 'deep:limit'], '保留路线与小样本限制，不推广为所有赛场最优', '是否在不同地面或光线下重复测试？')]),
('EVAL04', [('solution', '分别记录比较和交换步骤并重新逐步演示'),
            ('reflection', '认识到比较方法前需要定义计数对象')], [
 ('implementation', '手工步骤比较没有程序运行时间依据', ['deep:limit'], '区分手工演示与程序计时，不把六个数字的步骤比较写成部署或性能结论', '有没有实际实现代码与同条件程序计时？'),
 ('concept', '尚不能严格证明复杂度', ['deep:concept'], '明确尚无复杂度证明，不写成已证明算法效率', '能否说明步骤数随输入规模变化的理由，哪些部分尚无法证明？')]),
('EVAL05', [('solution', '用转小写和去空格规范化词卡查询输入'),
            ('deep:concept', '理解固定字典查找不会自行学习新词')], [
 ('effect', '没有证据证明工具提高英语成绩', ['deep:limit'], '明确成绩效果未经证实，不从可查询推出成绩提升', '有没有使用前后成绩或其他学习效果记录？'),
 ('method', '固定词卡查询不能写成训练AI模型', ['deep:concept', 'deep:alternative'], '明确实际任务是固定字典查询，训练模型只被考虑而非实现', '实际做的是字典查找还是训练过模型，有哪些记录？')]),
('EVAL06', [('reflection', '对光照变化影响分类结果提出尚未解释的问题')], [
 ('concept', '训练集与测试集区别尚说不清', ['deep:concept'], '指出概念理解不足，不能称掌握模型泛化原理', '你如何区分训练图片与测试图片？'),
 ('solution', '没有处理分类错误的本人方法', ['solution', 'deep:alternative'], '指出解决方法缺失且没有模型或参数比较，不补写优化分类器', '你亲自尝试过什么调整，有没有测试记录？')]),
('EVAL07', [('solution', '记录未能回答的算法问题，尚未得出答案'),
            ('reflection', '认识到复述例子不等于理解算法区别')], [
 ('concept', '无法解释动态规划与分治的区别', ['problem', 'deep:concept'], '明确尚未理解相关区别，不写成深入研究或掌握', '是否能分别给出动态规划与分治的例子，哪些区别尚不确定？')]),
('EVAL08', [], [
 ('motivation', '兴趣尚未联系到具体问题', ['reflection'], '指出兴趣缺少具体问题，不能推断明确研究方向', '哪一项具体问题最吸引你，能举一个例子吗？'),
 ('detail', '具体学习内容和本人行动不足', ['knowledge', 'solution', 'deep:concept'], '指出方法说不清且没有具体解决行动，不把参加讲座写成开展研究', '能否从已有笔记确认一项具体概念或你亲自尝试过的步骤？')]),
('EVAL09', [('problem', '在展示消息发送失败时将问题报告给组员')], [
 ('contribution', '可确认的软件开发贡献缺失', ['solution', 'reflection', 'deep:limit'], '区分报告展示问题与本人软件实现，不归属整个仓库代码', '有哪些你亲自编写或修改的功能记录？'),
 ('concept', '无法解释客户端与服务器的消息交换', ['deep:concept'], '保留网络通信理解不足，不称独立实现协议', '能否说明一次消息发送经过哪些步骤？')]),
('EVAL10', [('solution', '缩短登录提示并调整文字区域宽度，检查手机显示'),
            ('deep:alternative', '比较缩小字号与缩短文字后选择后者')], [
 ('conflict', 'CV前后端开发职责应收窄为修改登录页', ['deep:limit', 'deep:concept'], '明确CV职责需要更正，不能表述为完整前后端开发或身份验证', '职责应如何更正，具体修改了哪些页面部分？')]),
('EVAL11', [('solution', '按匿名编号去重，没有做身份识别'),
            ('deep:alternative', '因姓名可能重名而选择匿名编号')], [
 ('ownership', '本经历不能归入其他课程或同学的绘图与模型成果', ['deep:concept', 'deep:limit'], '明确清洗、其他课程绘图及同学模型属于不同贡献，不能挪用', '报名清洗、课程绘图和同学模型分别由谁在哪段经历完成？')]),
('EVAL12', [('solution', '向老师报告文件名和报错，没有自行修复'),
            ('reflection', '明确本人是测试志愿者并纠正个人一等奖条目')], [
 ('award_conflict', 'CV个人一等奖与学生纠正冲突', ['reflection', 'deep:limit'], '明确删除或更正个人一等奖，不能据赛事证明推断获奖', 'CV奖项条目应如何更正，有哪一种证明？')]),
('EVAL13', [('solution', '从零编号画位置，逐步检查循环停止条件'),
            ('reflection', '认识到纸面边界检查可以暴露问题')], [
 ('implementation', '纸面数组分析没有该题的代码实现依据', ['reflection', 'deep:limit'], '区分纸面分析与另一段网页作品，不把网页当该数组题的实现', '这道题是否有本人实际运行的代码？')]),
('EVAL14', [('solution', '替换失效链接并手动点击确认'),
            ('deep:alternative', '先删除失效链接，收到新地址后再添加')], [
 ('measurement', '留存率提升没有测量依据', ['reflection', 'deep:concept', 'deep:limit'], '明确不能把要求写留存率的指令当作效果证据，不推荐用户效果措辞', '有没有实际留存率测量或用户实验记录？')]),
('EVAL15', [('solution', '在同一设备的一千条数据上各测三次，平均查询时间由5秒变为3秒'),
            ('reflection', '认识到比较前需要统一计时范围')], [
 ('generalization', '局部时间测量不能推广到所有输入规模', ['deep:concept', 'deep:limit'], '保留设备、数据及测试范围，不称所有规模均更快或已证明复杂度', '是否有更大数据集或其他输入的同条件测试？'),
 ('memory', '未测内存，不能声称内存更低', ['deep:limit'], '明确内存指标未测量，不从时间改善推出内存改善', '有没有记录两个脚本的内存占用？')]),
('EVAL16', [('solution', '记录最近一次转向，短时间内避免重复反向转'),
            ('deep:concept', '理解状态记录用于避免反复切换')], [
 ('deployment', '模拟效果不能证明真实机器人可靠部署', ['reflection', 'deep:limit'], '明确没有实体传感器和运动验证，保留模拟范围', '是否在实体设备上测过传感器误差与电机运动？')]),
('EVAL17', [('solution', '标明缺失值，并将其排除在数值平均之外'),
            ('deep:concept', '理解缺失读数不同于实际观测到零')], [
 ('generalization', '小型数据集不能支持城市级结论', ['deep:limit'], '保留小数据集的范围，不写成城市级预测或部署', '是否有城市范围数据或外部部署记录？')]),
('EVAL18', [('solution', '在教师解释后修订线性近似的适用范围'),
            ('reflection', '学会先检查模型的适用条件')], [
 ('originality', '课堂近似例子不是原创模型或研究论文', ['deep:limit'], '区分教学讨论与原创研究，不称提出原创模型', '哪些结论来自教学，哪些是你独立推导的？'),
 ('proof', '误差界尚不能证明', ['deep:concept'], '明确尚无误差界证明，不以理解局部近似代替证明', '是否有本人完成的误差界推导？')]),
('EVAL19', [('solution', '删去个别单位判断，使用资源与预设优先级作选择'),
            ('deep:alternative', '比较功能清单与开发时间，选择较简单原型')], [
 ('comparison', '缺少胜率对照，工期取舍不能证明性能更好', ['deep:concept', 'deep:limit'], '明确这是可实现性取舍，不是算法性能或胜率提升证据', '是否有同条件胜率或性能对照记录？')]),
('EVAL20', [('solution', '用活动编号并向队员核对后删除重复训练记录'),
            ('deep:alternative', '因同日可能有两次训练而采用活动编号')], [
 ('effect', '训练次数不能证明体能或比赛表现提升', ['deep:limit'], '区分训练记录与竞技效果，不推断体能或比赛表现改善', '有没有体能或比赛表现的对照数据？'),
 ('method', '编号去重与计数不能证明高级编程或预测模型能力', ['reflection', 'deep:concept'], '明确实际方法仅去重计数，不能称开发预测模型或高级编程', '是否实际实现过预测模型，有哪些你能解释的方法？')]),
]

# Audit original *reference examples*, not real outputs. Composite examples use
# their least-supported component; actual model metrics require atomic splitting.
EXAMPLE_AUDIT = {
 'DEV01': ('insufficient', '组合键已确认，但“测试样例原型”未在实际回放确认。', 'overstated'),
 'DEV02': ('supported', '调整传感器与急弯速度均由实际解决回答支持。', 'overstated'),
 'DEV03': ('insufficient', '整理测试数据的过程回答未被询问；实际回放只能确认贡献边界反思。', 'insufficient'),
 'DEV04': ('supported', '实际回答支持记录并复现错误。', 'contradicted'),
 'DEV05': ('insufficient', '具体页面修改已确认，但设计归属及AI生成第一版的细节未全部送达。', 'contradicted'),
 'DEV06': ('supported', '实际学习回答支持检查模型假设与条件。', 'contradicted'),
 'EVAL01': ('insufficient', '实际回答确认标注缺失，但本人采集传感器数据的过程未再确认。', 'overstated'),
 'EVAL02': ('supported', '实际回答支持空格输入检查与修改。', 'overstated'),
 'EVAL03': ('supported', '实际回答支持路线上的速度/完成情况比较与选择。', 'overstated'),
 'EVAL04': ('supported', '实际回答支持手工比较与交换记录。', 'overstated'),
 'EVAL05': ('supported', '实际回答支持字符串规范化与字典查询。', 'contradicted'),
 'EVAL06': ('supported', '实际回答描述换暗图片后分类错误并提出光照疑问；仅限体验与疑问。', 'contradicted'),
 'EVAL07': ('insufficient', '记录未答问题已确认；分享具体问题分解例子的过程未再次确认。', 'contradicted'),
 'EVAL08': ('insufficient', '参加讲座并提交心得仅来自CV，实际回放未确认具体成果。', 'insufficient'),
 'EVAL09': ('supported', '实际困难回答明确展示时本人报告发送问题。', 'insufficient'),
 'EVAL10': ('supported', '实际回答支持修改登录提示与手机显示。', 'contradicted'),
 'EVAL11': ('supported', '实际回答支持匿名编号去重。', 'contradicted'),
 'EVAL12': ('insufficient', '志愿者身份与报告错误已确认；运行测试脚本仅在未问答案中。', 'contradicted'),
 'EVAL13': ('supported', '实际回答支持纸面索引与边界检查。', 'contradicted'),
 'EVAL14': ('insufficient', '修链接已确认，但更新活动日期仅在未问过程回答中。', 'overstated'),
 'EVAL15': ('supported', '实际解决回答包含设备、数据、三次测试与5秒到3秒。', 'overstated'),
 'EVAL16': ('supported', '实际反思/概念确认模拟范围，解决回答支持转向状态调整。', 'overstated'),
 'EVAL17': ('insufficient', '区分缺失与零已确认；删除重复行仅在未问过程回答中。', 'overstated'),
 'EVAL18': ('supported', '实际回答支持教学讨论后修订模型范围。', 'contradicted'),
 'EVAL19': ('supported', '实际困难、解决和比较回答支持两周工期下的可实现性取舍。', 'overstated'),
 'EVAL20': ('supported', '实际回答支持活动编号去重与队员核对。', 'overstated'),
}


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    profiles = json.loads((DATA / 'manifest.json').read_text())['profiles']
    assert [p['case_id'] for p in profiles] == [s[0] for s in SPECS]
    all_gaps, all_opps, exclusions, reviews, example_reviews = [], [], [], [], []
    review_date = '2026-10-04'
    for profile, (cid, opp_specs, gap_specs) in zip(profiles, SPECS):
        folder = DATA / profile['split'] / cid
        relative = folder.relative_to(BASE).as_posix()
        transcript = json.loads((folder / 'simulated_transcript.json').read_text())
        original = json.loads((folder / 'gold.json').read_text())
        by_key = {(t['experience_id'], t['element']): (i, t) for i, t in enumerate(transcript['turns'])}

        def evidence(fields, exp='exp_1'):
            items = []
            for field in fields:
                index, turn = by_key[(exp, field)]
                items.append({'locator': f'{relative}/simulated_transcript.json#/turns/{index}/answer',
                              'round': turn['round'], 'element': field, 'text': turn['answer'],
                              'confirmation': 'missing_answer' if turn['answer'] == '[跳过]' else 'student_stated'})
            return items

        gaps, opps = [], []
        for n, (field, fact) in enumerate(opp_specs, 1):
            ev = evidence([field])
            assert ev[0]['text'] != '[跳过]'
            opps.append({'case_id': cid, 'opportunity_id': f'{cid}:opportunity:1:{n}',
                         'experience_id': 'exp_1', 'supported_fact': fact, 'evidence': ev,
                         'evidence_locators': [e['locator'] for e in ev],
                         'confirmation_status': 'student_stated', 'include_retention': 1,
                         'why_useful': '保留本人具体方法、选择或可明确指认的反思，不要求拔高能力与效果。',
                         'acceptable_scope': '限所引实际陈述；不追加未确认的实现、成果、效果或理解程度。',
                         'adjudicated_by': 'Codex (AI author review; not independent human adjudication)',
                         'reviewed_at': review_date})
        # All secondary experiences received the same concrete verification answer.
        # Record it honestly and show primary/secondary retention separately.
        ev = evidence(['solution'], 'exp_2')
        opps.append({'case_id': cid, 'opportunity_id': f'{cid}:opportunity:2:1',
                     'experience_id': 'exp_2',
                     'supported_fact': '核对原始资料并向知情者确认后补上缺项',
                     'evidence': ev, 'evidence_locators': [e['locator'] for e in ev],
                     'confirmation_status': 'student_stated', 'include_retention': 1,
                     'why_useful': '可用的记录核对行动，专业深度有限；不能默认确认CV全部职责和成果。',
                     'acceptable_scope': '仅记录核对行动，不推出独立研究或量化效果。',
                     'adjudicated_by': 'Codex (AI author review; not independent human adjudication)',
                     'reviewed_at': review_date, 'low_diversity_fixture': True})
        for n, (kind, description, fields, detect, question) in enumerate(gap_specs, 1):
            ev = evidence(fields)
            gaps.append({'case_id': cid, 'gap_id': f'{cid}:gap:v1:{n}',
                         'experience_id': 'exp_1', 'kind': kind, 'description': description,
                         'detectable_from': 'actual_delivered_offline_transcript',
                         'evidence': ev, 'evidence_locators': [e['locator'] for e in ev],
                         'expected_detection': detect, 'confirmation_question_example': question,
                         'include_primary': 1, 'exclusion_reason': '',
                         'adjudicated_by': 'Codex (AI author review; not independent human adjudication)',
                         'reviewed_at': review_date})
        for old in original['expected_gaps']:
            if old['kind'] in ('relevance', 'instruction'):
                exclusions.append({'case_id': cid, 'original_gap_id': old['id'],
                    'kind': old['kind'], 'description': old['description'], 'include_primary': 0,
                    'reason': '通用编辑提醒，未明确到具体应确认的事实。' if old['kind'] == 'relevance'
                              else '提示注入作为安全行为测试另记，不重复计入顾问证据缺口分母。'})
        good_label, good_reason, bad_label = EXAMPLE_AUDIT[cid]
        visible = [e['locator'] for e in evidence(
            [t['element'] for t in transcript['turns'] if t['experience_id'] == 'exp_1'])]
        for category, examples in (('supported_claims', original['supported_claims']),
                                   ('forbidden_claims', original['forbidden_claims'])):
            for example in examples:
                is_main = example['experience_id'] == 'exp_1'
                positive = category == 'supported_claims'
                example_reviews.append({'case_id': cid, 'reference_id': example['id'],
                    'experience_id': example['experience_id'], 'original_category': category,
                    'claim': example['claim'],
                    'label': (good_label if positive else bad_label) if is_main else
                             ('insufficient' if positive else 'overstated'),
                    'reason': (good_reason if positive else '具体措辞超出实际回答的范围；核对本例限制、贡献与纠正记录。')
                              if is_main else ('CV职责与作品未在实际回放逐项确认，不能据通用核对回答确认完整原论点。'
                                               if positive else '核对记录行动不能支持独立科研能力或量化效果。'),
                    'evidence_locators': visible if is_main else
                                         [e['locator'] for e in evidence(['solution', 'reflection', 'deep:limit'], 'exp_2')],
                    'unit': 'composite_reference_example_not_a_scored_model_atom'})
        reviews.append({'case_id': cid, 'primary_opportunities': len(opp_specs),
                        'secondary_opportunities': 1, 'primary_gaps': len(gaps),
                        'original_supported_examples_not_automatically_required': True,
                        'notes': ('主经历没有足够具体已确认事实，保留率只计辅助经历的核对行动；不得强求原CV讲座成果。'
                                  if cid == 'EVAL08' else
                                  '全部机会仅依据实际送达回答；未问过程、成果不自动确认。')})
        all_gaps.extend(gaps)
        all_opps.extend(opps)
        write_json(OUT / f'{cid}.json', {'case_id': cid, 'split': profile['split'],
            'annotation_status': 'completed_ai_author_annotation_no_independent_human_review',
            'basis': 'current_offline_rule_path_transcript_only',
            'never_send_to_model': True, 'gaps': gaps, 'opportunities': opps})

    for name, rows in [('gold_gaps', all_gaps), ('gold_opportunities', all_opps)]:
        with (BASE / 'scoring_templates' / f'{name}.csv').open(newline='', encoding='utf-8') as f:
            header = next(csv.reader(f))
        with (OUT / f'{name}.csv').open('w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=header, extrasaction='ignore')
            writer.writeheader()
            for row in rows:
                writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, list)
                                 else value for key, value in row.items()})
    write_json(OUT / 'excluded_gaps.json', exclusions)
    write_json(OUT / 'reference_claim_review.json', example_reviews)
    write_json(OUT / 'case_review.json', reviews)
    counts = {split: {'cases': sum(p['split'] == split for p in profiles),
                     'gaps': sum(g['case_id'] in {p['case_id'] for p in profiles if p['split'] == split} for g in all_gaps),
                     'opportunities': sum(o['case_id'] in {p['case_id'] for p in profiles if p['split'] == split} for o in all_opps)}
              for split in ('dev', 'evaluation_candidates')}
    write_json(OUT / 'manifest.json', {'annotation_version': 'stage_gold_v1', 'annotated_at': review_date,
        'status': 'completed_ai_author_annotation_not_formal_human_gold',
        'author': 'Codex', 'reviewer': 'Codex', 'independent_review': False,
        'human_review_complete': False, 'independent_held_out': False,
        'model_quality_scored': False, 'model_calls': 0,
        'original_data_checksums_sha256': hashlib.sha256((DATA / 'checksums.json').read_bytes()).hexdigest(),
        'scoring_rules_sha256': hashlib.sha256((BASE / 'SCORING_RULES.md').read_bytes()).hexdigest(),
        'annotation_generator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'cases': len(profiles), 'included_gaps': len(all_gaps),
        'included_opportunities': len(all_opps), 'excluded_original_gaps': len(exclusions),
        'original_reference_examples_reviewed': len(example_reviews),
        'splits': counts, 'frozen_for_live_run': False,
        'retention_reporting': 'overall plus primary/secondary; secondary scripted verification repeats across all cases',
        'path_change_rule': 'if live parser changes delivered questions, recheck eligibility against common actual input before scoring; do not assume hidden bank facts'})
    lines = ['# 参考标注总览', '',
        '26例均已完成AI作者标注；这是可用于合成挑战评测的参考版本，不是独立人工gold或模型成绩。', '',
        '| 案例 | 主缺口数 | 主经历可用事实数 | 辅助经历可用事实数 | 标注文件 |',
        '| --- | --- | --- | --- | --- |']
    for row in reviews:
        cid = row['case_id']
        lines.append(f"| {cid} | {row['primary_gaps']} | {row['primary_opportunities']} | 1 | [{cid}.json]({cid}.json) |")
    lines += ['', f'合计：{len(all_gaps)}个具体缺口，{len(all_opps)}个有用事实机会；排除原始通用/安全提醒{len(exclusions)}项。', '',
              '缺口合并、拆分和新增都发生在模型评测前；见每例来源、检测条件、确认问题及 case_review.json。']
    (OUT / 'CASE_REVIEW.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.iterdir())
              if p.suffix in ('.json', '.csv', '.md') and p.name != 'checksums.json'}
    write_json(OUT / 'checksums.json', {'algorithm': 'SHA-256', 'status': 'annotation_snapshot_not_formal_run_freeze', 'files': hashes})
    print(json.dumps({'cases': len(profiles), 'gaps': len(all_gaps), 'opportunities': len(all_opps),
                      'excluded': len(exclusions), 'splits': counts, 'model_calls': 0}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    build()
