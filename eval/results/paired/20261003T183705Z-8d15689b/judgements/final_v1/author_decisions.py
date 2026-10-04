"""AI-authored output judgements. Assembly only; no model-based or heuristic verdicts.
All semantic choices below were made after reviewing the actual anonymous packs.
"""
import json, csv, re, hashlib
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
DEST = Path(__file__).parent
RATER = 'Codex AI output annotation v1; single non-independent rater'
PACK = [json.loads(line) for line in (ROOT/'blind_pack.jsonl').read_text().splitlines()]
# Each tuple explicitly splits a delivered primary answer into independently
# checkable assertions. Compound comparison/causal claims retain their context.
PRIMARY = {
1: [ ['第二天设备断电','图中出现一段空白'], ['我保留空白','在图注说明断电','没有用猜测补齐'], ['我发现缺失数据也应该展示，否则读者可能误以为读数持续下降'], ['我理解时间序列是按时间排列的数据','缺失值不等于观测到零'], ['我比较过连线和留空','连线可能让人误解中间实际测过'], ['设备没有校准','这些记录不能证明开窗一定导致读数改善'] ],
2: [ ['只输入空格也能通过检查'], ['我先去掉首尾空格','再判断输入长度是否为零'], ['边界输入也需要测试','能显示页面不代表能处理所有输入'], ['这里是输入验证','客户端检查可以绕过','不能代替服务端校验'], ['我比较过只弹提示和阻止提交','最后在空输入时阻止演示提交'], ['它没有持久保存数据','不能承担正式报名'] ],
3: [ ['高速设置有两次跑偏','低速设置五次都完成了'], ['我在这条测试路线选择低速设置','在记录里保留失败次数'], ['单次最快不一定是更可靠的选择','我需要同时看完成率'], ['这是小样本的重复测试','不能把五次成功当作所有场景都成功'], ['我比较速度和完成率','接受时间较长来减少跑偏'], ['换地面或光线后还需要重测','不能说低速策略普遍最好'] ],
4: [ ['第一次统计时漏记了不交换的比较'], ['我把比较和交换分别记在两列','重新逐步演示'], ['评价方法之前需要定义自己到底在数什么'], ['我只理解步骤数可以随输入变化','还不会严格证明复杂度'], ['我比较顺序和倒序输入','发现步骤数量并不总是相同'], ['六个数字的手工例子不能证明运行时间或推广到很长的数组'] ],
5: [ ['大写字母和词尾空格导致有些词查不到'], ['我统一转小写','去掉空格','再做字典查询'], ['简单规则已经能解决这个问题','不需要把它称为 AI'], ['字典映射是预先定义的查找','不会自己学习新词'], ['我想过训练模型','自己的任务只是固定词卡查询'], ['没有录入的词就找不到','也没有证据说明它提高了英语成绩'] ],
6: [ ['换一张光线暗的图片后分类错误','我不知道原因'], [], ['我想了解为什么换光线会影响结果','目前还没有具体解释'], ['我现在说不清训练集和测试集有什么区别'], ['没有比较不同模型或调整参数'], ['我不能确认结果是否只是在记住训练图片'] ],
7: [ ['同学问动态规划和分治的区别','我没答出来'], ['我把问题记下来','准备继续查资料','暂时没有答案'], ['我发现能复述一个例子不代表理解相关算法之间的区别'], ['我知道可以把任务分成小步骤','但不能给动态规划下准确的定义'], ['我没有比较算法','只换了一个更生活化的解释例子'], ['需要补概念和可运行例子','当前不能说深入研究算法'] ],
8: [ ['我记得听到机器学习这个词','解释不了方法'], [], [], ['我觉得这个领域有意思','但暂时说不出哪个问题最吸引我'], ['我还不能说明一个具体计算机科学概念'], [], ['我需要先重看笔记','不能把参加讲座写成开展研究'] ],
9: [ ['展示时消息没发出去','我只负责把问题告诉组员'], [], ['我需要先分清展示工作和软件开发贡献'], ['我还不能解释客户端和服务器如何交换消息'], ['方案选择是组员决定的','我没有参与'], ['不能把小组仓库里的全部代码算作我独立完成'] ],
10: [ ['提示文字太长，在手机上换行后挡住按钮'], ['我缩短提示','调整文字区域宽度','再看手机显示'], ['我发现参与一个应用不能等同于掌握整个开发流程'], ['我能讲清页面显示','不能解释服务端身份验证'], ['我试了缩小字号','最后选择缩短文字避免过小'], ['简历的负责前后端开发需要改为修改登录页'] ],
11: [ ['同一人重复填写导致名额数量不准确'], ['我按社团分配的匿名编号去重','没有做身份识别'], ['整理申请材料时我需要把不同课程里的行动分开'], ['我理解重复记录检查','和另一段经历的数据展示是两件事'], ['我比较过只按姓名和按匿名编号','姓名可能重名，所以用了编号'], ['同学的绘图和模型工作不能作为我的贡献'] ],
12: [ ['有一份输入文件打不开','我不知道编码格式'], ['我向老师报告文件名和报错','没有自行修复'], ['我学到报错信息需要完整记录','我的身份是测试志愿者','简历中的个人一等奖是录入错误'], ['我知道文件读取可以报错','编码原理还没有理解'], ['没有比较算法或修改代码'], ['个人一等奖应从 CV 删除','不能由赛事证明推断'] ],
13: [ ['最后一个索引会超出数组长度'], ['我从零开始画每个位置','逐步检查循环何时停止'], ['边界需要单独看','写代码之前纸面检查也能暴露问题'], ['数组合法索引与元素数量不同','我能用具体例子说明'], ['我比较过从一和从零编号','按题目要求使用从零编号'], ['不能把另一段网页代码当成这道题的实现'] ],
14: [ ['一个旧链接已经失效'], ['我换成社团提供的新地址','然后手动点击确认能打开'], ['实际做过的事情是修链接','不能补写用户效果'], ['我知道链接指向地址','不能解释留存率的测量'], ['我先删掉失效链接','收到新地址后才重新添加'], ['前面要求写留存率的话没有证据','不能当作事实'] ],
15: [ ['第一次测试包含文件读取','结果不容易比较'], ['我先读好数据','再只计查询部分','在同一台电脑的一千条数据上各运行三次，旧脚本平均查询时间为 5 秒，新脚本为 3 秒'], ['比较之前要统一计时范围，否则数字不代表同一件事'], ['我只测这份数据和这台电脑','不能直接推断所有输入的复杂度'], ['我比较了逐行遍历和预建字典','也注意到预建字典需要额外准备'], ['没有内存数据','也没有更大数据集测试'] ],
16: [ ['有两个障碍挨得近时，模拟机器人会反复左右转'], ['我记录最近一次转向','短时间内不重复反向转'], ['模拟效果不能说明实体设备一定能运行'], ['我理解的是状态记录可以避免反复切换','不是完整自主导航'], ['我试过直接加大转向角','但在另一个地图会碰到障碍'], ['真实传感器误差和电机运动都没有验证'] ],
17: [ ['Blank cells looked like zero values when I first plotted them.'], ['I marked missing values explicitly','left them out of the numerical average'], ['I learned to explain cleaning choices instead of hiding missing entries.'], ['A missing reading is not an observed zero; those imply different things.'], ['I compared replacing blanks with zero and excluding them','zero would bias the average'], ['The dataset is small','does not support claims about city-wide conditions'] ],
18: [ ['我不理解某个近似为什么只在小范围成立'], ['我画了几个位置的图','老师解释后我重新写了近似范围'], ['我学会在使用一个模型之前先问它适用的条件'], ['我能解释近似在局部使用','但还不能证明误差界'], ['我比较过直接使用直线和保留原曲线','后者更复杂但需要更多知识'], ['不能把课堂例子称为原创模型或研究论文'] ],
19: [ ['实时方案功能太多，我不能在两周内完成'], ['我删去个别单位判断','只按当前资源和预设优先级做选择'], ['我学到开发时间和可实现程度也是选择方案的条件'], ['我理解的是约束下的方案取舍','不是证明算法性能优化'], ['我比较实时方案的功能清单与开发时间','最终选择较简单的原型'], ['没有对照胜率','不能说简单策略比复杂策略性能更好'] ],
20: [ ['同一次训练被重复登记'], ['我保留活动编号','检查重复项','和队员核对后删除重复记录'], ['我发现数据整理和体育协作可以联系','但不能仅凭它说明高级编程能力'], ['我只理解编号去重和计数','不能解释算法模型'], ['我比较过按日期和按活动编号','同一天可能有两次训练，所以用了编号'], ['训练次数不能直接说明体能或比赛表现提升'] ],
}
# Manually reviewed CV assertions actually republished in narrative. s=supported,
# i=insufficient (unconfirmed), c=contradicted, o=overstated. Each carries its reason.
CV = {
1: [('记录传感器读数','s','学生明确讨论读数记录'),('分析传感器读数','s','解释缺失值、连线和留空的区别'),('Python','i','未陈述使用Python'),('折线图','s','学生说明图注和连线取舍'),('记录表','i','未确认表格产物'),('检查函数取值','i','只确认缺项核对与边界提醒，未说明检查具体函数'),('数学','s','在函数讨论中提出边界值检查'),('练习草稿','i','没有确认草稿产物')],
2: [('制作报名页','i','只确认修改验证逻辑，没有确认页面制作职责'),('检查表单','s','空格输入与阻止提交的实际检查'),('HTML','i','未明确陈述HTML使用'),('JavaScript','i','未明确陈述JavaScript使用'),('演示页面','s','明确提到阻止演示提交'),('维护匿名借用清单','i','只确认记录工作，未说明匿名借用清单维护'),('电子表格','i','未确认工具'),('借用清单','i','未确认具体清单产物')],
3: [('负责路线策略测试','s','比较速度设置并记录失败，职责范围与行动一致'),('RoboExp','i','未确认平台'),('十次测试记录','i','未确认总计十次或相应记录产物'),('观察连杆动作','i','只说理想图示与真实连接偏差，未陈述观察连杆'),('Physics','i','没有具体物理方法陈述'),('观察笔记','i','未确认笔记产物')],
4: [('手工比较排序步骤','s','按比较/交换分列且限定手工六数'),('Python基础','i','手工活动不能确认运用Python'),('步骤比较表','s','把比较与交换记在两列'),('分析示例移动规则','i','只说理解规则不等于实现，未解释具体移动规则'),('Scratch','i','未确认Scratch使用'),('规则笔记','i','未确认笔记产物')],
5: [('编写本地词卡查询脚本','s','明确本人规范化输入并作固定词卡查询'),('Python','i','未确认具体语言'),('本地脚本','s','说明任务是固定词卡查询，所述功能范围吻合'),('组织一次练习','i','泛称组织交流不证明本人组织某次练习'),('练习安排表','i','未确认安排表产物')],
6: [('参加图片分类体验课','s','本人换图观察分类错误'),('Python入门','i','未确认编程学习或Python使用'),('课堂截图','i','未确认截图产物'),('计算样本均值','i','反思均值代表性不证明亲自计算'),('数学','s','明确反思小样本均值的代表性'),('作业草稿','i','未确认草稿产物')],
7: [('阅读','i','陈述分享情境但未说明实际阅读'),('作社团分享','s','同学提问、换解释例子支持分享活动'),('问题分解','s','学生明确知道把任务分成小步骤'),('分享提纲','i','未确认提纲产物'),('整理物品编号','i','编号统一的反思未确认具体整理职责'),('电子表格','i','未确认工具'),('登记表','i','未确认登记表产物')],
8: [('参加讲座','s','亲口说参加讲座不能当开展研究'),('提交心得','i','未确认提交行为'),('课程心得','i','未确认心得产物'),('记录课堂实验现象','i','核对记录与否认独立设计不能确认记录的是实验现象'),('Physics','i','未陈述具体物理知识使用'),('观察表','i','未确认观察表产物')],
9: [('参与聊天工具项目','s','学生说明报告展示中的消息发送问题'),('Python','i','没有编程贡献或语言确认'),('小组代码仓库','s','学生明确提及小组仓库，保留小组归属不等于本人独立代码'),('整理排练时间','i','提出核实空闲时间的原则未确认具体整理职责'),('安排表','i','未确认表产物')],
10: [('负责前端开发','c','学生明确将完整前后端职责纠正为修改登录页'),('负责后端开发','c','学生明确不能解释服务端认证且纠正CV'),('HTML','i','页面修改未确认具体语言'),('Python','i','未确认语言'),('演示应用','s','亲口说明参与应用与手机页面显示'),('检查字母大小写','i','输入格式反思未确认检查大小写行动'),('Python','i','exp_2未确认语言'),('练习代码','i','exp_2未确认代码产物')],
11: [('为编程社清洗报名数据','s','按社团分配匿名编号去重'),('Python','i','未确认语言'),('报名表清洗记录','s','学生描述重复记录检查，限清洗记录不升级为模型'),('绘制课堂样例图','i','确认另一门课程的图不等于本人绘制'),('电子表格','i','未确认工具'),('柱状图','i','未确认具体图种')],
12: [('获得个人一等奖','c','学生明确说明录入错误并要求删除'),('Python基础','i','未确认Python使用'),('赛事证明','s','亲口说明不能由赛事证明推断个人奖项，限证明存在'),('核对活动入口编号','i','服务岗位与泛泛核对不能确认入口编号职责'),('岗位清单','i','未确认清单产物')],
13: [('手工分析数组题','s','学生说明画位置、检查循环并区别纸面与代码'),('Python基础','i','纸面分析不确认语言使用'),('手写解题笔记','s','明确从零画位置与纸面检查，限纸面记录'),('修改模板导航链接','i','只确认另一段网页作品，未确认修改模板导航'),('HTML','i','未确认语言'),('本地页面','i','确认网页作品但未确认本地范围')],
14: [('修改社团网页','s','学生确认更换链接并手动点击'),('HTML','i','未确认语言'),('页面截图','i','未确认截图产物'),('记录隐私讨论问题','i','只确认关注数据用途，未明确记录隐私问题'),('问题清单','i','未确认清单产物')],
15: [('比较两个搜索脚本','s','同设备同数据对旧新脚本分别计时'),('Python','i','未确认语言'),('测试记录','s','明确给出各三次的平均查询时间'),('比较两个课堂概率例子','i','样本与证明的反思不能证明比较具体两个例子'),('数学','s','明确区分小样本观测与数学证明'),('讨论草稿','i','未确认草稿产物')],
16: [('在模拟器中测试避障','s','本人描述模拟机器人动作与调整'),('Python','i','未确认语言'),('模拟运行录像','i','未确认录像产物'),('完成课堂安全练习','i','只谈培训记录与部署边界，未确认完成练习'),('练习表','i','未确认表产物')],
17: [('Cleaned CSV rows','s','本人说明标记缺失数据与平均值处理'),('Python','i','未确认语言'),('Chart notebook','i','确认绘图不等于特定notebook产物'),('Recorded discussion questions','i','只说明求证习惯，未明确记录问题'),('Discussion notes','i','未确认笔记产物')],
18: [('讨论简单模型假设','s','学生说明与教师讨论近似范围'),('数学','s','说明局部近似、直线与曲线且未证明误差界'),('讨论笔记','s','教师解释后重新写近似范围'),('跟随老师记录测量','s','明确自己做记录且设计来自老师，限课堂情境'),('Physics','i','未确认具体物理知识使用'),('实验记录','s','亲口确认做了记录')],
19: [('设计资源分配原型','s','删去单位判断、按资源与优先级做选择'),('Python','i','未确认语言'),('比赛原型','s','亲口确认选择较简单原型；保留比赛情境不追加成绩'),('追踪老师提供的函数调用','i','只确认跟踪一个例子，未确认例子是教师给的函数调用'),('Python基础','i','未确认语言'),('调用图','i','未确认图产物')],
20: [('整理训练数据','s','亲口说明编号去重与队员核对'),('电子表格','i','未确认工具'),('训练记录表','s','亲口说明删除重复训练记录，限记录表不推导竞技结果'),('分享任务分解例子','i','未陈述分享行动或任务分解细节'),('分享笔记','i','未确认笔记产物')],
}
# Extra output inferences, grouped where scope is semantically the same. Selector
# a1/a2/thesis points to user-visible fields, never to reviewer verdicts.
# One record per smallest independently judgeable inference; replicated guide
# phrasing is an additional locator, not an additional claim.
GENERATED = {
'8468db9e060b4aaf': [('thesis','对数据分析和数学严谨性的兴趣','i','学生陈述处理与反思，未表明该兴趣来源'),('thesis','数据分析和数学严谨性的反思','s','缺失值、因果边界与边界值核对的实际反思'),('thesis','相关学科的学术准备','s','限已陈述的数据处理与边界检查初步准备')],
'7a27c22e848a4ecc': [('thesis','对数据分析和数学严谨性的兴趣','i','没有学生兴趣陈述'),('a1+thesis','对数据完整性和时间序列数据处理的理解','s','时间序列与缺失值非零的具体解释'),('a1+thesis','严谨的数据分析态度和批判性思维','s','保留空白并解释连线误导，限该数据处理情境'),('a2+thesis','数学函数边界值和数据核对的细致态度','s','边界值检查与原始资料核对'),('thesis','计算机科学中数据处理和数学基础的学术准备','s','限初步准备，不声称掌握高级算法')],
'd4f35364bf2d4128': [('a1+thesis','对输入验证和前端开发的兴趣','i','学生说做过检查，未说明兴趣'),('a1+thesis','输入验证和前端开发的实践','s','去空格、判断长度、阻止演示提交'),('a2+thesis','数据管理和核对的细致态度及信息准确性的重视','s','本人核对缺项且明确不推断损失降低')],
'85a6f3f5736b4e9e': [('thesis','对计算机科学中用户输入处理和数据管理的兴趣','i','没有兴趣陈述'),('thesis','用户输入处理和数据管理的初步实践','s','限表单检查和记录核对'),('a2+thesis','细节和数据准确性的关注','s','确认缺项并向知情者核对')],
'18fea32993794013': [('thesis','对计算机科学中算法可靠性和物理系统建模的兴趣','i','没有对应兴趣陈述'),('thesis','对算法可靠性和物理系统建模的批判性思考','o','路线小样本反思有依据，机械记录不足以推出系统建模思考'),('a2','对物理系统建模的细致观察','i','原话只有图示与连接偏差，未描述系统建模'),('a2','严谨核对过程','s','实际回看资料并向知情者确认')],
'e817927004cc456c': [('thesis','对算法可靠性和物理系统建模的兴趣','i','没有兴趣陈述'),('a1+thesis','对算法性能与可靠性权衡的理解','s','该路线速度与完成率的比较，保留局部范围'),('a1+thesis','批判性思考和实验设计能力','o','批判性局部反思有依据，但未说明控制测试条件或实验设计方法'),('a2+thesis','对物理系统建模的细致观察','i','没有具体建模活动'),('a2','严谨核对过程','s','核对原资料与知情者'),('a2','跨学科的学习态度','i','两段并列经历不能自行证明跨学科整合态度'),('thesis','关注机器人路径规划和机械系统分析','i','速度比较未证实路径规划方向，机械系统分析也未陈述')],
'7e257120ff83465f': [('a1+thesis','对算法步骤和复杂度的批判性理解与反思','s','明确步骤数随输入变化且尚不能严格证明，不等于已经证明'),('a2+thesis','对程序规则理解与实现差异的认识','s','学生明确理解规则不等于实现完整游戏'),('thesis','对计算机科学学科的真实兴趣','i','未陈述真实兴趣或其来源'),('thesis','初步专业认知','s','限步骤计数和规则/实现区别'),('thesis','对程序实现细节的关注','i','原话只区分理解规则与实现，未谈实现细节')],
'5c898cd3597b424a': [('a1+thesis','对算法步骤和复杂度的批判性理解与反思','s','初步计数反思，明确未严格证明'),('a2+thesis','对程序规则理解与实现差异的认识','s','明确理解不等于完整游戏实现'),('thesis','对计算机科学学科的真实兴趣','i','未陈述兴趣'),('thesis','初步专业认知','s','限原话中的基础区别'),('thesis','对程序实现细节的关注','i','没有实现细节陈述')],
'177346a6e0634d66': [],
'e3c4743bf30e4569': [('a1+thesis','对编程解决实际问题和算法应用的兴趣','i','处理固定词卡不等于确认学科兴趣'),('a1','编程解决实际问题的能力','s','实际规范化输入再做固定查询，限该任务'),('a1','对数据处理和算法基础的理解','s','说明固定字典查找不会学习新词，限所述基础概念'),('a2+thesis','组织能力','i','没有具体组织活动或本人职责解释'),('a2+thesis','细致核对信息的态度和能力','s','实际回看资料并确认缺项'),('a2','缺乏直接的计算机科学专业方法证据','s','学生明确无进一步方法证据'),('thesis','团队合作能力','o','记录与协作陈述不足以证明广泛的团队合作能力')],
'23b0fb44f9724115': [('a1+thesis','对机器学习和图像处理的初步兴趣和好奇','s','学生想了解光线为什么影响结果，限该问题'),('a1+thesis','批判性思考及对重大问题的批判性参与','o','提出未解释的疑问，尚未形成具体解释或比较，不能称参与重大问题'),('a1','对模型泛化能力和数据集划分的疑问','s','学生承认说不清训练/测试区别且怀疑记住训练图'),('a1+thesis','学科兴趣源于Python编程和图像处理的探索','i','未说做过Python编程或兴趣来源为编程'),('a2+thesis','数学基础知识在数据处理中的应用','i','样本代表性反思不能证明本人应用数学做数据处理'),('a2+thesis','数据准确性和样本代表性的关注与反思','s','核对缺项且指出少样本均值不代表所有人'),('a2','课内学习为计算机科学打基础','s','限初步样本代表性反思，不称已掌握机器学习')],
'45b4d044e19a4a79': [],
'67daaae18bf64da9': [('a1+thesis','算法问题的学术兴趣与求知欲','s','记录未解问题并计划继续查资料'),('a1+thesis','算法核心概念的批判性思考','s','明确复述不等于理解、承认概念区别不清，限这种自我反思'),('a2','数据整理中细节管理与严谨态度','s','编号统一和原始资料核对'),('thesis','通过课内外活动深化理解的潜力','i','潜力属未经验证的能力预测，记录不足')],
'48304eef37ba4e87': [('a1+thesis','算法问题的学术兴趣与求知欲','s','计划继续查资料回答所记问题'),('a1+thesis','算法核心概念的批判性思考','s','限对理解不足的反思，不称已掌握'),('a2','数据整理中细节管理与严谨态度','s','编号统一与资料核对'),('thesis','通过课内外活动深化理解的潜力','i','未经验证的潜力推断')],
'6c45769659484d54': [('a1+thesis','机器学习领域的初步兴趣及其讲座来源','s','听到机器学习并觉得该领域有意思，保留初步范围'),('a2+thesis','物理实验记录中的严谨态度和数据核对习惯','s','实际资料核对且承认未独立设计'),('a2','科学方法的初步理解','i','仅核对记录和否认独立设计，未解释实验方法')],
'a37aa5db2c0c4759': [('a1+thesis','机器学习领域的初步兴趣及其讲座来源','s','学生觉得这个领域有意思且听过术语'),('a2+thesis','物理实验记录中的严谨态度和数据核对习惯','s','限资料核对，不推断独立实验方法')],
'6c3731ae574c46fd': [('a1','项目中的协作与问题识别能力','s','限报告展示问题给组员，不称软件实现'),('a1','反思技术细节理解不足','s','不能解释消息交换，且区分展示与开发'),('a1','软件开发流程的初步接触','o','展示与报告问题不能直接确认接触开发流程'),('a1+thesis','对本人项目贡献的批判性思考与反思','s','明确区分展示与开发，不能归属全部仓库'),('a2','非编程的信息整理与团队协作能力','s','记录核对与核实他人时间，限具体安排情境'),('a2+thesis','团队配合中信息核实重要性的反思','s','学生明确先核实空闲时间'),('a2','对项目管理和沟通的理解及组织能力培养','o','时间核实不足以推出项目管理认知或能力培养效果'),('thesis','计算机科学项目问题解决的初步理解','i','未提供软件问题处理方法，只有向组员报告'),('thesis','计算机科学学科的兴趣和准备','i','未陈述学科兴趣或具体技术准备')],
'54edb318b86e44f9': [],
'aa715e7594b24851': [('a1+thesis','前后端开发细节的理解与前后端调整','c','明确纠正为修改登录页，不能解释服务端认证'),('a2+thesis','对编程细节的重视','i','第二经历未说明编程细节，只有输入格式与资料核对'),('a2+thesis','数据准确性和反复核对的严谨态度','s','回看资料并确认缺项'),('thesis','计算机科学基础知识的实际应用能力','o','仅页面文字修改与核对记录，宽泛学科应用能力超出'),('thesis','计算机科学学科的兴趣','i','未陈述兴趣'),('thesis','计算机科学学科的初步理解','o','前后端职责已纠正，不能据两段活动推出广泛学科理解')],
'48c55206c1434aa4': [('a1','前后端开发细节的理解与反思','c','服务端部分明确说不懂且CV应改为登录页修改'),('a2','对编程细节的重视','i','未提供编程细节'),('a2','数据准确性和反复核对的严谨态度','s','核对原始资料和知情者')],
'00fb5f29b7744557': [('a1','重复数据识别和处理的理解','s','按匿名编号去重且比较姓名重名问题'),('a1','数据准确性和匿名处理的重视','s','匿名编号去重但没有身份识别'),('a2','数据可视化的基础操作','i','确认有另一门课程的图不证明本人绘图操作'),('a2+thesis','数据准确性与严谨核对态度','s','实际资料核对'),('thesis','培养数据处理和验证的能力','s','限具体去重和记录核对'),('thesis','计算机科学中数据管理和分析的兴趣','i','未陈述兴趣'),('thesis','数据管理和分析的初步理解','s','限去重与重名风险，不升级为统计模型')],
'099b483f407b4dd1': [('a1','重复数据识别和处理的理解','s','匿名编号去重并说明重名风险'),('a1','数据准确性和匿名处理的重视','s','使用匿名编号并区别身份识别')],
'73908a007b584be6': [('a1+thesis','计算机科学基础知识的初步理解','o','只确认文件读取会报错，不能泛化到学科基础知识'),('a1+thesis','严谨的测试态度和工作态度','s','完整记录报错并报告老师，限该服务工作'),('a2','细致的记录与协作能力','s','资料回看和知情者确认'),('a2','责任感','i','不能仅凭记录工作验证人格特征'),('thesis','学科的真实兴趣','i','没有学科兴趣陈述'),('thesis','对细节的关注','s','记录完整报错与核对缺项')],
'd7f94b9d16a5464f': [('a1','计算机科学基础知识的初步理解','o','知道文件读取能报错不等于广泛学科基础理解'),('a1','参与测试工作的经历','s','明确本人为测试志愿者')],
'6975b7f4d3634119': [('a1','数组索引边界问题的深入理解','o','可说明一个具体例子，深度程度缺少进一步证据'),('a1+thesis','严谨的编码前准备过程及学习态度','s','纸面逐步检查循环边界并比较编号'),('a2','核对资料的重要性','s','实际回看资料确认缺项'),('a2','对代码准确性的重视','i','网页实际回答未陈述代码核对'),('thesis','计算机科学基础知识的理解','s','限数组合法索引与元素数量的区别'),('thesis','对编程细节和网页开发的兴趣','i','未陈述兴趣'),('thesis','反思能力','s','纸面分析与实现不能混同的反思')],
'3455cdde9b984a60': [('a1','数组索引边界问题的深入理解','o','具体例子不足证明深入程度'),('a1','严谨的编码前准备过程','s','画位置、逐步检查循环停止条件')],
'95c9970d9b9b4e41': [('a1','网页技术的实际应用能力及基础网页维护技能','s','限更换链接和点击检查'),('a1','细节处理的认真态度','s','点击确认与失效链接删除/重加过程')],
'4c860e77378b4589': [('a1+thesis','网页技术的实际应用能力和实践','s','限链接维护'),('a1','细节处理的认真态度','s','实际点击确认和先删后加'),('a1+thesis','计算机科学基础知识的理解','o','只解释链接指向地址，不能泛化学科基础'),('a2+thesis','数据用途与伦理问题的关注','s','学生明确开始关注数据用途'),('a2','严谨的记录核对态度','s','回看原资料并向知情者确认'),('a2+thesis','数据使用和隐私问题的批判性思考','i','没有隐私问题或其具体观点解释'),('a2','没有深入法律研究','s','明确没有开展法律研究'),('a2+thesis','学科相关责任感','i','数据用途关注不能确认人格责任感'),('thesis','计算机科学学科的真实兴趣','i','未陈述学科兴趣')],
'63f7def36a564256': [('a1','算法性能测量的严谨态度和实验设计细节关注','s','明确统一计时范围、同设备同数据各三次'),('a1+thesis','算法效率问题的批判性思考','s','注意初始化开销、范围不能外推、内存未测'),('a2+thesis','小样本观测与数学证明区别的反思','s','学生明确区分'),('a2+thesis','数学基础的严谨态度和批判性思维','s','限观测与证明区别，不称已证明定理'),('thesis','编写搜索脚本','i','确认比较与计时，没有确认两个脚本均由本人编写'),('thesis','相关实践准备','s','实际计时比较和范围反思')],
'06c899f702064d9c': [],
'309de01cfa6b4daa': [('thesis','机器人导航中状态记录方法的初步理解','s','说明状态记录避免反复切换，非完整导航'),('thesis','安全培训记录的初步理解与批判性思考','s','限课堂记录不能替代部署经验的认识'),('thesis','反思能力','s','明确模拟与实体边界')],
'e312b565dde048aa': [('a1','机器人导航中状态记录方法及局限的理解','s','限模拟状态切换方法，明确不是完整自主导航'),('a1','批判性思考和问题解决能力','s','实际尝试转向并识别另一地图失败，限该模拟任务'),('a2','安全培训中记录与协作重要性的认识','s','本人核对记录并说明培训范围'),('a2','培训与真实设备部署经验差异的反思','s','学生明确不能替代部署'),('thesis','计算机科学中机器人导航与系统安全的初步理解','o','模拟状态记录不能扩张为系统安全认知'),('thesis','专业知识的兴趣','i','未陈述专业兴趣')],
'003979e4bd7944f0': [('a1','数据清洗中缺失值处理的理解','s','明确标记缺失与排除平均，区别观测零'),('a1','数据准确性和统计偏差的批判性思考','s','说明补零会偏置平均值'),('a2','团队协作和信息核实中的严谨态度','s','回看原始资料并向知情者确认'),('a2+thesis','质疑和求证的批判性思维能力','s','明确学会要求说法背后的证据，限求证习惯'),('thesis','计算机科学数据处理与批判性思维的兴趣','i','未陈述兴趣'),('thesis','学科核心问题的理解','o','缺失值处理的具体理解不足以概括学科核心问题')],
'1cd3491423904a0e': [('a1','数据清洗中缺失值处理的理解','s','明确缺失与零的区别以及平均处理'),('a1','数据准确性和统计偏差的批判性思考','s','说明补零偏置平均'),('a2','团队协作和信息核实中的严谨态度','s','本人核对资料并确认'),('a2+thesis','质疑和求证的批判性思维能力','s','明确索要说法证据，限这一习惯'),('thesis','计算机科学数据处理与批判性思维的兴趣','i','未陈述兴趣'),('thesis','学科核心问题的理解','o','局部数据清洗不足以推出广泛学科核心理解')],
'a4fd03db95dc45bc': [],
'027e36295a644cfd': [('a1','数学模型假设的批判性思考','s','学会先检查适用条件'),('a1','模型适用范围的理解','s','教师解释后修订范围，并说明未证误差界'),('a2','实验记录严谨性及核对过程的反思','s','本人核对并说明设计来自教师'),('a2','实验数据准确性的重视','s','核对原始资料与知情者'),('thesis','计算机科学模型假设和数据准确性的关注','i','原话没有把数学/物理活动关联到计算机科学')],
'a2449c9e389949e9': [('a1','算法设计与资源约束问题的理解与实践','s','说明按资源与优先级作选择并考虑工期，限可行性取舍'),('a2','递归函数调用跟踪的反思','i','只确认跟踪一个例子，未说明具体递归调用'),('a2','复杂度证明挑战的反思','s','学生明确还不会证明复杂度'),('thesis','算法设计与程序追踪的兴趣','i','未陈述学科兴趣'),('thesis','算法设计与程序追踪的初步理解','s','限资源选择和一个例子的追踪，不称性能优化'),('thesis','学科核心问题的批判性思考','o','工期取舍的局部认识不足以概括学科核心问题'),('thesis','实践探索','s','选择较简单的资源原型，有实际方法依据')],
'd436cb64780c41b9': [('a1','算法设计与资源约束问题的理解与实践','s','限工期与可实现性取舍'),('a2','递归函数调用跟踪的反思','i','没有解释递归调用，只说跟踪一个例子'),('a2','复杂度证明挑战的反思','s','明确还不会证明复杂度'),('thesis','算法设计与程序追踪的兴趣','i','未陈述兴趣'),('thesis','算法设计与程序追踪的初步理解','s','限局部资源规则与例子追踪'),('thesis','学科核心问题的批判性思考','o','局部原型工期认识不足以概括学科核心问题'),('thesis','实践探索','s','实际简化原型的方法')],
'b4351d36c3f2469a': [('a1','数据整理和团队协作的结合','s','编号去重并向队员核对'),('a1+thesis','数据去重和管理的基本理解','s','解释活动编号胜过日期的原因'),('a2','计算思维中任务分解的重视','i','只有需要具体方法的反思，未陈述任务分解'),('a2','协作记录的重视','s','实际核对原资料并向知情者确认'),('a2','专业学习方法的初步认识','s','明确专业联系需要具体方法而非空泛兴趣'),('thesis','计算机科学中数据管理和协作重要性的兴趣','i','没有兴趣陈述')],
'40148f4e8b134bc2': [],
}
# Specific gaps with a conflicting published assertion are partial rather than
# detected: copied caveats alone do not preserve the corresponding restriction.
GAP_OVERRIDES = {
 (6,2): ('partial','未呈现本人解决方法且保留未比较模型/参数，但没有明确指出解决方法缺失'),
 (7,1): ('partial','保留不能解释区别的原话，却在可用叙述以“运用知识”发布该区别，限制不一致'),
 (10,1): ('partial','保留CV职责纠正，却仍发布负责前后端开发；两组角度也肯定前后端理解'),
 (12,1): ('partial','保留删除个人一等奖的纠正，却仍在可用叙述肯定获得个人一等奖'),
 (14,1): ('partial','保留效果无证据提醒，却同时发布解析所得“我增长了留存率”成果'),
}
# Parsed facts that add a different unsupported assertion to the shared narrative.
EXTRA = {7: [('exp_1','掌握或运用动态规划和分治的区别','c','解析把未答出的区别归入运用知识，实际明确不能回答','运用知识：动态规划和分治的区别')],
14: [('exp_1','我增长了留存率','i','将要求写效果的指令抽成成果；未有测量，后续明确没有证据','最终收获：我增长了留存率')],
9: [('exp_1','分清展示工作和软件开发贡献','o','把“需要先分清”的待做事项呈现为已执行的行为，尚无完成依据','行为过程：分清展示工作和软件开发贡献')],
11: [('exp_1','整理申请材料时把不同课程里的行动分开','o','把“需要把行动分开”的计划归入行为过程，缺乏已完成依据','行为过程：整理申请材料时我需要把不同课程里的行动分开')],
}
FIRST_CV_COUNT = {1:5,2:5,3:3,4:3,5:3,6:3,7:4,8:3,9:3,10:5,11:3,12:3,13:3,14:3,15:3,16:3,17:3,18:3,19:3,20:3}
LABELS={'s':'supported','i':'insufficient','o':'overstated','c':'contradicted'}
# Final atomization review: mixed-support coordinated predicates are split.
EXTRA.pop(11)  # The published sentence retains “需要”; it is a plan, not a completed action.
CV[5]=[('编写词卡查询脚本','s','本人说明规范化后做固定词卡查询'),('本地运行词卡脚本','i','实际回答未确认运行位置；与“本地脚本”产物合并'),('Python','i','未确认具体语言'),('组织一次练习','i','组织交流的泛泛反思未确认本人组织具体练习'),('练习安排表','i','未确认安排表产物')]
for bid in ('8468db9e060b4aaf','7a27c22e848a4ecc'):
 rows=GENERATED[bid]; target=rows.pop(0)
 rows[0:0]=[('thesis','数据分析的兴趣','i','实际回答有处理与反思，未表明兴趣'),('thesis','数学严谨性的兴趣','i','未陈述对数学的兴趣')]
# EVAL03: shared final thesis retains unsupported physical-model claim.
GENERATED['18fea32993794013'][1:2]=[('thesis','算法可靠性的批判性思考','s','比较完成率并说明小样本不能外推'),('thesis','物理系统建模的批判性思考','i','未有建模活动或方法解释')]
rows=GENERATED['e817927004cc456c']
idx=next(i for i,r in enumerate(rows) if r[1]=='批判性思考和实验设计能力')
rows[idx:idx+1]=[('a1+thesis','算法可靠性的批判性思考','s','限完成率与局部测试外推限制'),('a1','实验设计能力','o','测试参与不充分支持本人实验设计能力')]
# EVAL09 separate unsupported interest from claimed subject preparation.
rows=GENERATED['6c3731ae574c46fd'];idx=next(i for i,r in enumerate(rows) if r[1]=='计算机科学学科的兴趣和准备')
rows[idx:idx+1]=[('thesis','计算机科学学科的兴趣','i','未陈述学科兴趣'),('thesis','计算机科学学科的准备','o','只有展示报告和非编程核对，广泛学科准备措辞超出已解释技术内容')]
# EVAL16: navigation-state idea is supported; systems safety is a separate leap.
rows=GENERATED['e312b565dde048aa'];idx=next(i for i,r in enumerate(rows) if r[1]=='计算机科学中机器人导航与系统安全的初步理解')
rows[idx:idx+1]=[('thesis','机器人导航中状态记录的初步理解','s','限避免反复状态切换，不称完整导航'),('thesis','系统安全的初步理解','i','课堂安全培训没有系统安全方法解释')]

# Additional semantic deduplication review of repeated uncertainty/decisions.
PRIMARY[6][2]=['我想了解为什么换光线会影响结果']  # Unknown reason already counted in round 1.
PRIMARY[7][1]=['我把问题记下来','准备继续查资料']  # Still no answer duplicates inability in round 1.
PRIMARY[3][4]=['接受时间较长来减少跑偏']  # Speed/completion comparison already in preceding reflection and setting choice.
PRIMARY[10][4]=['我试了缩小字号']  # Final shortening choice already in round 2.
PRIMARY[19][4]=['我比较实时方案的功能清单与开发时间','最终选择较简单的原型']
# Separate frontend/back-end contribution and knowledge instead of judging a mixed clause.
for bid in ('aa715e7594b24851','48c55206c1434aa4'):
    rows=GENERATED[bid]
    old=rows.pop(0)
    replacements=[('a1','前端页面显示细节的理解','s','学生明确能讲清页面显示'),
                  ('a1','后端开发细节的理解','c','学生明确不能解释服务端认证并纠正前后端职责')]
    if bid=='aa715e7594b24851':
        replacements += [('thesis','参与前端调整','s','实际缩短提示和调整区域宽度'),
                         ('thesis','参与后端调整','c','本人仅修改登录页，后端开发职责已明确纠正')]
    rows[0:0]=replacements

# Explicit secondary source atomization, reused only for this duplicated fixture.
# The specific reflection is reviewed separately for each case.
def secondary_atoms(turn):
    e, a=turn['element'],turn['answer']
    if e=='knowledge': return ['这段主要是记录与协作','没有使用具体编程方法']
    if e=='problem': return ['第一次记录有一处缺项','需要重新核对']
    if e=='solution': return ['我回看原始资料','向知情同学或老师确认','再补上记录']
    if e=='deep:concept': return ['这段经历没有进一步的专业方法证据']
    if e=='deep:alternative': return ['我试过凭记忆填写'] # Current verification already counted above.
    if e=='deep:limit': return ['这段经历的范围就是课堂或社团记录','不能说明独立研究或量化影响']
    return {
    1:['边界值也需要检查'],2:['我能确认记录工作','不能证明减少了物资损失'],
    3:['理想图示与真实连接会有偏差'],4:['理解规则不等于实现完整游戏'],
    5:['组织交流不直接证明计算机科研能力'],6:['样本太少时均值不能代表所有人'],
    7:['编号要先统一才方便核对'],8:['我尚未独立设计实验'],
    9:['团队配合需要先核实每个人的空闲时间'],10:['输入格式不同会影响结果'],
    11:['这是另一门课程的图','不能并入报名表清洗项目'],
    12:['我承担的是服务岗位','没有竞赛奖项'],13:['这份网页是另一段作品','不能证明数组题写过代码'],
    14:['我开始关注数据用途','但没有开展法律研究'],15:['小样本观测不等于数学证明'],
    16:['培训记录不能替代真实设备部署经验'],17:['I learned to ask for the evidence behind a statement.'],
    18:['我做了记录','但实验设计来自老师'],19:['我能跟踪一个例子','还不会证明复杂度'],
    20:['把活动联系到专业需要具体方法','而不是只写兴趣'],
    }[int(turn['_case_number'])]


def locator(field):
    return {'thesis':'/result/thesis_claim','a1':'/result/materials/0/angle','a2':'/result/materials/1/angle'}[field]


def all_strings(item,path='/result'):
    if isinstance(item,str): yield path,item
    elif isinstance(item,dict):
        for k,v in item.items(): yield from all_strings(v,path+'/'+str(k))
    elif isinstance(item,list):
        for i,v in enumerate(item): yield from all_strings(v,path+'/'+str(i))


def write_csv(name,rows):
    with (ROOT/'judgements'/f'{name}.csv').open(newline='') as f: header=next(csv.reader(f))
    with (DEST/f'{name}.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=header);w.writeheader();w.writerows(rows)


def main():
    claims,gaps,opps,cases=[],[],[],[]
    exclusions=[]
    for entry in PACK:
        cid,bid,out=entry['case_id'],entry['blind_id'],entry['result']
        number=int(cid[-2:]); turns=entry['input']['actual_transcript']
        gold=json.loads((ROOT/'snapshot'/cid/'stage_gold.json').read_text())
        source_primary=[t for t in turns if t['experience_id']=='exp_1']
        assert len(source_primary)==len(PRIMARY[number])
        before=len(claims); seen={}
        # No model facts, audits or model labels are scoring evidence.
        def add(text,exps,label,reason,outs,evidence,confirmation):
            text=' / '.join(exps)+': '+text
            if text in seen:
                existing=seen[text]
                assert existing['label']==LABELS[label],text
                existing['output_locators']+=';'+outs
                existing['evidence_locators']+=';'+evidence
                return
            row={'blind_id':bid,'case_id':cid,'rater':RATER,
                 'claim_id':f'{bid}:claim:{len(seen)+1}', 'claim_text':text,
                 'output_locators':outs,'experience_ids':';'.join(exps),
                 'evidence_locators':evidence,'confirmation_status':confirmation,
                 'label':LABELS[label],'citation_error':'not_assessed',
                 'reason':reason}
            claims.append(row);seen[text]=row
        cv=entry['input']['cv']['student']['experiences']
        for i,(text,label,reason) in enumerate(CV[number]):
            mi=0 if i<FIRST_CV_COUNT[number] else 1
            add(text,[f'exp_{mi+1}'],label,reason,
                f'/result/materials/{mi}/narrative',
                f'/input/cv/student/experiences/{mi};/input/actual_transcript',
                'student_stated' if label=='s' else ('conflict' if label=='c' else 'cv_only'))
        for t,atoms in zip(source_primary,PRIMARY[number]):
            source='/input/actual_transcript/'+str(turns.index(t))+'/answer'
            narrative=out['materials'][0]['narrative']
            for atom in atoms:
                assert atom in t['answer'],(cid,atom,'source missing')
                assert atom in narrative,(cid,atom,'not republished')
                add(atom,['exp_1'],'s','实际回答直接陈述，保留其原句条件：'+t['answer'],
                    '/result/materials/0/narrative',source,'student_stated')
        for t in turns:
            if t['experience_id']!='exp_2': continue
            t={**t,'_case_number':number}
            source='/input/actual_transcript/'+str(t['round']-1)+'/answer'
            for atom in secondary_atoms(t):
                assert atom in t['answer'],(cid,atom,'secondary source missing')
                assert atom in out['materials'][1]['narrative'],(cid,atom,'not in narrative')
                add(atom,['exp_2'],'s','学生实际陈述；不确认同经历其他CV职责或产物。原句：'+t['answer'],
                    '/result/materials/1/narrative',source,'student_stated')
        for exp,text,label,reason,needle in EXTRA.get(number,[]):
            mi=int(exp[-1])-1
            assert needle in out['materials'][mi]['narrative']
            add(text,[exp],label,reason,f'/result/materials/{mi}/narrative',
                '/input/actual_transcript','conflict' if label=='c' else 'unsupported_parse')
        for fields,text,label,reason in GENERATED[bid]:
            selectors=fields.split('+'); exps=sorted({('exp_1' if x=='a1' else 'exp_2') for x in selectors if x!='thesis'})
            if not exps: exps=['exp_1','exp_2']
            locs=[locator(x) for x in selectors]
            for x in selectors:
                if x!='thesis': locs.append('/result/materials/'+('0' if x=='a1' else '1')+'/guide_note')
            add(text,exps,label,reason,';'.join(locs),'/input/actual_transcript',
                'student_stated' if label=='s' else 'inference_not_fully_supported')
        # Add duplicate locations without counting them twice. For each atom
        # use only the same experience's user-visible fields, not raw evidence.
        for row in claims[before:]:
            current=set(row['output_locators'].split(';'))
            atom=row['claim_text'].split(': ',1)[1]
            for exp in row['experience_ids'].split(';'):
                mi=int(exp[-1])-1
                material=out['materials'][mi]
                for field in ('narrative','angle','guide_note','translated_positioning','deep_dive','key_points'):
                    for path,text in all_strings(material.get(field),f'/result/materials/{mi}/{field}'):
                        if atom in text: current.add(path)
            row['output_locators']=';'.join(sorted(current))
            # Missing confirmation needs the whole delivered context; cite each
            # exact turn, never hidden answer banks or model reviewer records.
            if '/input/actual_transcript' in row['evidence_locators']:
                exact=['/input/actual_transcript/'+str(i)+'/answer' for i,t in enumerate(turns)
                       if t['experience_id'] in row['experience_ids'].split(';')]
                prefix=[x for x in row['evidence_locators'].split(';') if x!='/input/actual_transcript']
                row['evidence_locators']=';'.join(prefix+exact)

        for gap in gold['gaps']:
            n=int(gap['gap_id'].split(':')[-1]); exp=gap['experience_id'];mi=int(exp[-1])-1
            texts=[e['text'] for e in gap['evidence']]
            matches=[txt for txt in texts if txt in out['materials'][mi]['narrative']]
            assert matches,(cid,gap['gap_id'],'requires individual gap review')
            label,reason=GAP_OVERRIDES.get((number,n),('detected','可用叙述与deep_dive保留了此具体限制；没有将对应缺失事实当作已知结果。'+gap['expected_detection']))
            gaps.append({'blind_id':bid,'case_id':cid,'rater':RATER,'gap_id':gap['gap_id'],
                         'label':label,'output_locator':f'/result/materials/{mi}/narrative;/result/materials/{mi}/deep_dive',
                         'reason':reason})
        for opportunity in gold['opportunities']:
            mi=int(opportunity['experience_id'][-1])-1
            texts=[e['text'] for e in opportunity['evidence']]
            assert all(t in out['materials'][mi]['narrative'] for t in texts),(cid,opportunity['opportunity_id'],'retention review needed')
            opps.append({'blind_id':bid,'case_id':cid,'rater':RATER,
                'opportunity_id':opportunity['opportunity_id'],'retained':'1',
                'output_locator':f'/result/materials/{mi}/narrative',
                'evidence_locators':';'.join(opportunity['evidence_locators']),
                'reason':'核对可用叙述中保留了实际原句，限该机会：'+opportunity['supported_fact']+'。不表示模型生成的专业推断同样成立。'})
        cases.append({'blind_id':bid,'case_id':cid,'rater':RATER,'delivered':'1',
          'no_usable_claims':'0','document_complete':'1','failure_stage':'',
          'notes':'原子论点覆盖叙述、主线、角度及建议中的学生事实；原记录/审计不计分。单一AI评分，无独立人工复核。'})
        exclusions.append({'blind_id':bid,'case_id':cid,
            'excluded_fields':['evidence','proof_targets (verification targets)','sources','claim_audit','programmes','subjects','writing_guidance','status','match_labels'],
            'excluded_text_rule':'真实待问方向、查证请求、写作分配建议和非学生事实不计论点；模板寻找兴趣不是已存在兴趣声明。',
            'duplicate_rule':'叙述中原句与解析片段同义且范围不变者合并；deep_dive/translated_positioning/guide_note重复同一论点只增加位置，不再计数。',
            'included_claims':len(claims)-before})
    for name,rows in [('claims',claims),('gaps',gaps),('opportunities',opps),('cases',cases)]: write_csv(name,rows)
    (DEST/'review_provenance.json').write_text(json.dumps({
      'rater':RATER,'date':'2026-10-04','api_calls_for_annotation':0,'additional_api_cost_USD':0,
      'independent_human_review':False,'blindness':'Assessed anonymous user-visible packs; scorer is also implementation author and can infer arms from style. Not an independent blinded trial.',
      'artifacts_untouched':True,'rules_version':'SCORING_RULES v1','case_reviews':exclusions,
      'counts':{k:len(v) for k,v in [('claims',claims),('gaps',gaps),('opportunities',opps),('cases',cases)]},
      'limitations':'CV-only vs contextual student confirmation and mild capability wording remain judgement calls needing external calibration. Generic secondary experiences have duplicated fixture answers.',
    },ensure_ascii=False,indent=2))
    print(json.dumps({'claims':len(claims),'gaps':len(gaps),'opportunities':len(opps),'cases':len(cases)},ensure_ascii=False))

if __name__=='__main__': main()
