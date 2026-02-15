# Facebook加小组模块 - 参数配置表

## 1. 阶段加小组配额表

```
阶段 | 天数   | 每次添加数量 | 每日最多 | 添加间隔(分钟)
-----|--------|--------------|----------|----------------
1    | 0-3    | 0-1          | 1        | -
2    | 4-7    | 1-2          | 2        | 30-60
3    | 8-15   | 1-2          | 3        | 20-40
4    | 16-25  | 2-3          | 4        | 15-30
5    | 26-45  | 2-4          | 5        | 10-25
6    | 46+    | 3-5          | 6        | 10-20
```

**说明：**
- 每次添加数量：单次运行添加的小组数
- 每日最多：当天累计最多添加数量
- 添加间隔：两次添加小组之间的间隔时间

## 2. 小组搜索参数

```
参数                 | 值
---------------------|------------------
搜索方式             | 关键词搜索
每次搜索滚动次数     | 3-8次
每次滚动间隔         | 2-5秒
每次搜索获取小组数   | 10-20个
最小成员数过滤       | 客户端自定义（默认100）
搜索结果去重         | 是
```

**成员数配置说明：**
```
- 最小成员数：客户端UI输入框设置，默认100人
```

## 3. 小组筛选流程

```
步骤 | 动作                     | 说明
-----|--------------------------|---------------------------
1    | 关键词搜索小组           | 输入关键词，点击搜索
2    | 滚动获取小组列表         | 滚动3-8次，获取10-20个小组
3    | 提取小组信息             | 序号+名称+链接+成员数
4    | 过滤成员数               | 过滤<100人的小组，加入排除库
5    | 数据库去重检查           | 检查链接是否已存在
6    | AI判断小组相关性         | 返回符合要求的序号列表
7    | 保存AI选中的小组         | 保存到精准小组池
8    | 保存AI未选中的小组       | 保存到排除库（永久）
9    | 按配额添加小组           | 根据阶段配额添加
10   | 继续或结束               | 未达配额继续搜索
```

**关键改进：**
- 步骤8：AI未选中的小组也保存到排除库
- 原因：避免重复调用AI分析相同小组
- 排除库永久保存，减少AI调用成本

## 4. AI判断参数

### 4.1 判断小组相关性

**输入格式：**
```json
{
  "groups": [
    {"id": 1, "name": "小组名称1", "members": 5000},
    {"id": 2, "name": "小组名称2", "members": 3000},
    {"id": 3, "name": "小组名称3", "members": 8000}
  ],
  "industry": "行业关键词",
  "target_quota": 2
}
```

**输出格式：**
```json
{
  "selected_ids": [1, 3],
  "reason": "小组1和3与行业相关"
}
```

**AI Prompt模板：**
```
你是一个Facebook小组筛选助手。

任务：从以下小组列表中，筛选出与"{industry}"行业相关的小组。

小组列表：
{groups_list}

要求：
1. 只返回与行业高度相关的小组序号
2. 最多返回{target_quota}个小组
3. 按相关性从高到低排序
4. 返回JSON格式：{"selected_ids": [1, 3], "reason": "原因"}
5. 如果没有相关小组，返回：{"selected_ids": [], "reason": "无相关小组"}

请分析并返回结果：
```

### 4.2 回答小组验证问题

**场景：** 加入小组时需要回答验证问题

**输入格式：**
```json
{
  "group_name": "小组名称",
  "questions": [
    {
      "id": 1,
      "question": "你为什么想加入这个小组？",
      "type": "text"
    },
    {
      "id": 2,
      "question": "你从事什么行业？",
      "type": "text"
    },
    {
      "id": 3,
      "question": "你是买家还是卖家？",
      "type": "choice",
      "options": ["买家", "卖家", "两者都是"]
    }
  ],
  "user_profile": {
    "industry": "行业",
    "role": "角色",
    "purpose": "目的"
  }
}
```

**输出格式：**
```json
{
  "answers": [
    {
      "id": 1,
      "answer": "我对这个行业很感兴趣，希望能学习更多知识"
    },
    {
      "id": 2,
      "answer": "我从事外贸行业"
    },
    {
      "id": 3,
      "answer": "买家"
    }
  ]
}
```

**AI Prompt模板：**
```
你是一个Facebook小组验证问题回答助手。

场景：用户想加入小组"{group_name}"，需要回答以下验证问题。

用户信息：
- 行业：{industry}
- 角色：{role}
- 目的：{purpose}

验证问题：
{questions_list}

要求：
1. 回答要真诚、自然，不要过于营销
2. 回答要符合用户的行业和角色
3. 回答长度适中（20-80字）
4. 选择题直接返回选项文本
5. 避免使用"我想推销"、"我是卖家"等直白表述
6. 使用"学习"、"交流"、"了解"等友好词汇
7. 返回JSON格式：{"answers": [{"id": 1, "answer": "回答内容"}]}

请生成回答：
```

**回答策略：**
```
问题类型                 | 回答策略
------------------------|---------------------------
为什么加入              | 强调学习、交流、了解行业
从事什么行业            | 如实回答，但不过度营销
买家还是卖家            | 优先选择"买家"或"两者都是"
如何知道小组            | 朋友推荐、搜索发现
期望获得什么            | 行业知识、经验分享、资源
是否同意规则            | 同意
联系方式                | 暂不提供（避免被拒）
```

## 5. 数据库表结构

### groups_pool 表（精准小组池）
```
字段名              类型            说明
------------------- --------------- ---------------------------
id                  BIGINT          主键自增
group_name          VARCHAR(200)    小组名称
group_url           VARCHAR(500)    小组链接(唯一)
group_members       INT             小组成员数
marketing_account   VARCHAR(100)    营销账号ID(NULL=未分配)
joined_at           TIMESTAMP       加入时间

INDEX idx_url (group_url)
INDEX idx_account (marketing_account)
INDEX idx_status (status)
```

### groups_excluded 表（排除小组库）
```
字段名              类型            说明
------------------- --------------- ---------------------------
id                  BIGINT          主键自增
group_url           VARCHAR(500)    小组链接(唯一)
group_name          VARCHAR(200)    小组名称
group_members       INT             小组成员数
reason              VARCHAR(100)    排除原因
created_at          TIMESTAMP       创建时间

INDEX idx_url (group_url)
```

**排除原因类型：**
```
- "成员数不足" : 成员数<100
- "AI判断不相关" : AI判断不符合行业
```

### account_group_history 表（账号小组历史）
```
字段名              类型            说明
------------------- --------------- ---------------------------
id                  BIGINT          主键自增
account_id          VARCHAR(100)    账号ID
group_url           VARCHAR(500)    小组链接
action_type         VARCHAR(50)     动作(assigned/joined/left)
action_time         TIMESTAMP       动作时间

INDEX idx_account (account_id)
INDEX idx_group (group_url)
```

## 6. 去重检查逻辑

```
检查项                         | 查询表           | 条件
-------------------------------|------------------|------------------
小组链接是否在精准池           | groups_pool      | group_url = ?
小组链接是否在排除库           | groups_excluded  | group_url = ?
小组是否已分配给当前账号       | groups_pool      | group_url = ? AND marketing_account = ?
小组是否已分配给其他账号       | groups_pool      | group_url = ? AND marketing_account IS NOT NULL
```

**去重规则：**
```
IF 小组在排除库:
    跳过该小组
ELSE IF 小组在精准池 AND 已分配给当前账号:
    跳过该小组
ELSE IF 小组在精准池 AND 已分配给其他账号:
    跳过该小组
ELSE IF 小组在精准池 AND 未分配:
    可以分配给当前账号
ELSE:
    新小组，可以添加
```

## 7. 账号删除后的小组回收

**触发条件：**
```
- 账号被封禁
- 账号被删除
- 账号状态异常
```

**回收逻辑：**
```sql
-- 将该账号的所有小组状态改为pending
UPDATE groups_pool 
SET status = 'pending', 
    marketing_account = NULL,
    assigned_at = NULL
WHERE marketing_account = '被删除的账号ID'
  AND status IN ('assigned', 'joined')
```

**回收后状态：**
```
- status: pending (待分配)
- marketing_account: NULL (未分配)
- assigned_at: NULL (清空分配时间)
- joined_at: 保留 (保留加入时间记录)
```

## 8. 添加小组行为参数

```
参数                 | 最小值 | 最大值 | 单位
---------------------|--------|--------|--------
点击小组链接间隔     | 2      | 6      | 秒
加载小组页面等待     | 3      | 8      | 秒
点击加入按钮间隔     | 2      | 5      | 秒
加入后等待           | 3      | 10     | 秒
返回搜索页面间隔     | 2      | 6      | 秒
```


## 10. API接口定义

### 检查小组是否可用

```
POST /api/check-group-available

请求：
{
  "group_url": "https://facebook.com/groups/xxx",
  "account_id": "account_001"
}

响应：
{
  "available": true,
  "reason": "可以添加",
  "in_pool": false,
  "in_excluded": false,
  "assigned_to": null
}
```

### 提交小组信息

```
POST /api/submit-group

请求：
{
  "group_name": "小组名称",
  "group_url": "https://facebook.com/groups/xxx",
  "group_members": 5000,
  "marketing_account": "account_001",
  "industry_match": true
}

响应：
{
  "success": true,
  "group_id": 12345,
  "status": "assigned"
}
```

### 批量添加到排除库

```
POST /api/add-to-excluded

请求：
{
  "groups": [
    {
      "group_url": "https://facebook.com/groups/xxx",
      "group_name": "小组名称",
      "group_members": 5000,
      "reason": "AI判断不相关"
    }
  ]
}

响应：
{
  "success": true,
  "added_count": 1
}
```

### 回答小组验证问题

```
POST /api/answer-group-questions

请求：
{
  "group_name": "小组名称",
  "questions": [
    {
      "id": 1,
      "question": "你为什么想加入这个小组？",
      "type": "text"
    }
  ],
  "user_profile": {
    "industry": "外贸",
    "role": "采购",
    "purpose": "寻找供应商"
  }
}

响应：
{
  "success": true,
  "answers": [
    {
      "id": 1,
      "answer": "我对这个行业很感兴趣，希望能学习更多知识"
    }
  ]
}
```

```
POST /api/recycle-groups

请求：
{
  "account_id": "account_001"
}

响应：
{
  "success": true,
  "recycled_count": 5,
  "message": "已回收5个小组到待分配状态"
}
```

## 11. 执行流程伪代码

```javascript
// 获取账号阶段和配额
stage = getAccountStage(accountRegisterDate)
quota = getGroupQuota(stage)
targetCount = random(quota.min, quota.max)

// 检查今日已添加数量
todayAdded = getTodayAddedCount(accountId)
if (todayAdded >= quota.dailyMax) {
    console.log("今日配额已满")
    return
}

remainingQuota = quota.dailyMax - todayAdded
targetCount = min(targetCount, remainingQuota)

console.log(`目标添加${targetCount}个小组`)

addedCount = 0
searchAttempts = 0
maxSearchAttempts = 5

while (addedCount < targetCount && searchAttempts < maxSearchAttempts) {
    // 搜索小组
    keyword = getNextKeyword()
    console.log(`搜索关键词: ${keyword}`)
    
    // 滚动获取小组列表
    scrollTimes = random(3, 8)
    groups = []
    
    for (i = 0; i < scrollTimes; i++) {
        newGroups = extractGroupsFromPage()
        groups = groups.concat(newGroups)
        scrollDown()
        sleep(random(2, 5))
    }
    
    console.log(`获取到${groups.length}个小组`)
    
    // 过滤成员数
    groups = groups.filter(g => g.members >= 100)
    console.log(`过滤后剩余${groups.length}个小组`)
    
    // 数据库去重
    availableGroups = []
    for (group of groups) {
        checkResult = await checkGroupAvailable(group.url, accountId)
        if (checkResult.available) {
            availableGroups.push(group)
        }
    }
    
    console.log(`去重后剩余${availableGroups.length}个小组`)
    
    if (availableGroups.length === 0) {
        searchAttempts++
        console.log("没有可用小组，继续搜索")
        continue
    }
    
    // 准备AI判断数据
    aiInput = {
        groups: availableGroups.map((g, index) => ({
            id: index + 1,
            name: g.name,
            members: g.members
        })),
        industry: "行业关键词",
        target_quota: targetCount - addedCount
    }
    
    // AI判断
    aiResult = await callAI(aiInput)
    selectedIds = aiResult.selected_ids
    
    console.log(`AI选择了${selectedIds.length}个小组: ${selectedIds}`)
    
    // 保存AI选中的小组到精准池
    selectedGroups = []
    for (id of selectedIds) {
        group = availableGroups[id - 1]
        selectedGroups.push(group)
    }
    
    // 保存AI未选中的小组到排除库（永久保存）
    unselectedGroups = availableGroups.filter((g, index) => 
        !selectedIds.includes(index + 1)
    )
    
    for (group of unselectedGroups) {
        await addToExcluded({
            group_url: group.url,
            group_name: group.name,
            group_members: group.members,
            reason: "AI判断不相关"
        })
    }
    console.log(`已将${unselectedGroups.length}个不相关小组加入排除库`)
    
    if (selectedGroups.length === 0) {
        searchAttempts++
        console.log("AI判断无符合小组，继续搜索")
        continue
    }
    
    // 添加选中的小组
    for (group of selectedGroups) {
        if (addedCount >= targetCount) break
        
        // 点击小组链接
        clickGroupLink(group.url)
        sleep(random(2, 6))
        
        // 等待页面加载
        sleep(random(3, 8))
        
        // 点击加入按钮
        joinResult = clickJoinButton()
        sleep(random(2, 5))
        
        if (joinResult.needQuestions) {
            // 需要回答验证问题
            console.log(`小组需要回答验证问题`)
            
            // 提取问题
            questions = extractQuestions()
            
            // 调用AI生成答案
            answersResult = await callAI_AnswerQuestions({
                group_name: group.name,
                questions: questions,
                user_profile: {
                    industry: "行业",
                    role: "角色",
                    purpose: "目的"
                }
            })
            
            // 填写答案
            for (answer of answersResult.answers) {
                fillAnswer(answer.id, answer.answer)
                sleep(random(1, 3))
            }
            
            // 提交申请
            submitApplication()
            sleep(random(2, 5))
            
            console.log(`已提交验证问题答案，等待审核`)
        }
        
        if (joinResult.success || joinResult.needQuestions) {
            // 保存到精准小组池
            await submitGroup({
                group_name: group.name,
                group_url: group.url,
                group_members: group.members,
                marketing_account: accountId,
                industry_match: true
            })
            
            addedCount++
            console.log(`成功添加小组: ${group.name}`)
            
            // 添加间隔
            if (addedCount < targetCount) {
                interval = random(quota.intervalMin, quota.intervalMax) * 60
                sleep(interval)
            }
        } else {
            console.log(`添加失败: ${group.name}`)
            // 添加失败也保存到排除库
            await addToExcluded({
                group_url: group.url,
                group_name: group.name,
                group_members: group.members,
                reason: "加入失败"
            })
        }
        
        // 返回搜索页面
        goBackToSearch()
        sleep(random(2, 6))
    }
    
    searchAttempts++
}

console.log(`完成，共添加${addedCount}个小组`)
console.log(`已将不相关小组永久保存到排除库，避免重复AI分析`)
```

## 12. 关键优化点

### 风控友好设计

1. **渐进式配额**
   - 阶段1：0-1个/次，1个/天
   - 阶段6：3-5个/次，6个/天

2. **添加间隔**
   - 阶段1：无（只添加1个）
   - 阶段2：30-60分钟
   - 阶段6：10-20分钟

3. **搜索行为自然化**
   - 滚动次数随机：3-8次
   - 滚动间隔随机：2-5秒
   - 每次获取10-20个小组

4. **AI判断后永久保存**
   - 符合的小组保存到精准池
   - 不符合的小组保存到排除库
   - 避免重复AI分析
   - 减少AI调用成本

6. **AI自动回答验证问题**
   - 检测验证问题弹窗
   - AI生成真诚自然的答案
   - 自动填写并提交
   - 提高小组通过率

7. **账号删除自动回收**
   - 小组自动回到待分配状态
   - 可以分配给其他账号
   - 避免资源浪费

6. **去重机制完善**
   - 精准池去重
   - 排除库去重
   - 账号级别去重
