# Facebook转发帖子到小组模块 - 参数配置表

## 1. 阶段转发配额表

```
阶段 | 天数   | 每次转发数量 | 每日最多 | 转发小组间隔(秒)
-----|--------|--------------|----------|------------------
1    | 0-3    | 0            | 0        | -
2    | 4-7    | 0            | 0        | -
3    | 8-15   | 0            | 0        | -
4    | 16-25  | 1-2          | 3        | 30-60
5    | 26-45  | 2-3          | 5        | 20-40
6    | 46+    | 3-5          | 8        | 15-30
```

**说明：**
- 前3个阶段禁止转发（风控要求）
- 每次转发数量：单次运行转发的帖子数
- 每日最多：当天累计最多转发数量
- 转发小组间隔：同一个帖子转发到不同小组的间隔时间

## 1.1 转发目标分配

```
转发目标     | 概率   | 说明
-------------|--------|---------------------------
转发到小组   | 100%   | 必定执行，转发到1-3个小组
转发到快拍   | 50%    | 50%概率执行，24小时消失，风控低
转发到动态   | 60%    | 60%概率执行，个人主页动态
```

**说明：**
- 每个转发目标独立判断概率
- 可以同时转发到多个目标
- 执行顺序随机，避免固定模式
- 示例：一个帖子可能同时转发到小组+快拍+动态

**执行示例：**
```
帖子A：
- 转发到小组（100%）✓
- 转发到快拍（50%）✓
- 转发到动态（60%）✗
结果：转发到小组和快拍

帖子B：
- 转发到小组（100%）✓
- 转发到快拍（50%）✗
- 转发到动态（60%）✓
结果：转发到小组和动态

帖子C：
- 转发到小组（100%）✓
- 转发到快拍（50%）✓
- 转发到动态（60%）✓
结果：转发到小组、快拍和动态
```

## 2. 公共主页帖子获取参数

```
参数                 | 值
---------------------|------------------
主页来源             | 客户端配置主页链接列表
每次访问主页数       | 1-2个
每次滚动间隔         | 2-5秒
每个主页获取帖子数   | 最近30条
帖子发布时间过滤     | 30天内
帖子去重             | 是
```



## 4. 帖子筛选流程

```
步骤 | 动作                     | 说明
-----|--------------------------|---------------------------
1    | 选择访问方式             | 根据阶段和概率选择
2    | 访问公共主页             | 通过选定方式进入主页
3    | 滚动获取帖子列表         | 随机获取最近30条
6    | 随机选择帖子             | 从可用帖子中随机选择
7    | 阅读帖子                 | 10-30秒
8    | 概率点赞                 | 80-100%概率
9    | 决定转发目标             | 小组70%/快拍50%/动态60%
10   | 执行转发                 | 根据目标执行转发
```

## 4. AI判断参数

### 4.1 判断帖子质量

**输入格式：**
```json
{
  "posts": [
    {
      "id": 1,
      "content": "帖子内容摘要",
      "publish_time": "2小时前",
      "likes": 120,
      "comments": 35
    },
    {
      "id": 2,
      "content": "帖子内容摘要",
      "publish_time": "1天前",
      "likes": 80,
      "comments": 20
    }
  ],
  "industry": "行业关键词",
  "target_quota": 3
}
```

**输出格式：**
```json
{
  "selected_ids": [1, 2],
  "reason": "帖子1和2内容质量高，适合转发"
}
```

```

## 5. 小组选择策略

```
参数                 | 值
---------------------|------------------
小组来源             | groups_pool表（已加入的小组）
每次转发小组数       | 1-3个
小组选择策略         | 轮次+权重
小组冷却时间         | 24小时
同一帖子同一小组     | 不重复转发
轮次管理             | 是
```

**轮次管理规则：**
```
1. 每个账号维护一个轮次编号（round_number）
2. 每次转发时，优先选择本轮未转发的小组（round_shared=0）
3. 当所有小组本轮都已转发（round_shared=1）时，进入下一轮
4. 下一轮开始：round_number+1，所有小组round_shared重置为0
5. 确保每个小组在每轮中都被转发一次
```

**小组权重规则（本轮未转发的小组）：**
```
条件                         | 权重
----------------------------|--------
本轮未转发                  | 100（必选）
本轮已转发                  | 0（跳过）
白名单小组                  | 0（跳过，不能转发）
最近7天未转发过             | +20
最近3天未转发过             | +10
```

## 5. 转发行为参数

```
参数                 | 最小值 | 最大值 | 单位
---------------------|--------|--------|--------
访问主页等待         | 2      | 6      | 秒
搜索输入时长         | 2      | 5      | 秒
搜索结果等待         | 2      | 4      | 秒
滚动获取帖子间隔     | 2      | 5      | 秒
随机选择帖子思考     | 1      | 3      | 秒
打开帖子等待         | 2      | 6      | 秒
阅读帖子时长         | 10     | 30     | 秒
点赞概率             | 80%    | 100%   | -
点赞后等待           | 2      | 5      | 秒
点击分享按钮间隔     | 2      | 5      | 秒
选择分享目标等待     | 2      | 4      | 秒
选择小组等待         | 2      | 4      | 秒
输入转发文案时长     | 3      | 8      | 秒
点击发布间隔         | 2      | 5      | 秒
发布后等待           | 3      | 8      | 秒
转发下一个小组间隔   | 15     | 30     | 秒
关闭帖子返回主页     | 2      | 6      | 秒
选择下一个帖子间隔   | 5      | 15     | 秒
```

**说明：**
- 搜索输入时长：模拟手动输入主页名称
- 阅读帖子时长：模拟真人阅读，10-30秒
- 点赞概率：80-100%概率点赞（不是每次都点）
- 选择分享目标等待：选择小组/快拍/动态的思考时间
- 转发下一个小组间隔：同一帖子转发到不同小组的间隔
- 选择下一个帖子间隔：转发完一个帖子后，选择下一个帖子的间隔

## 7. 转发文案生成

### 7.1 文案生成策略

```
转发目标     | 是否需要文案 | 说明
-------------|--------------|---------------------------
转发到小组   | 必须         | AI生成，10-50字
转发到动态   | 必须         | AI生成，10-80字
转发到快拍   | 不需要       | 快拍通常不添加文案
```

### 7.2 AI生成文案（小组）

**输入格式：**
```json
{
  "post_content": "原帖内容摘要",
  "group_name": "小组名称",
  "caption_type": "group_share",
  "industry": "行业关键词"
}
```

**输出格式：**
```json
{
  "caption": "这个内容很有价值，分享给大家",
  "length": 15
}
```

**AI Prompt模板：**
```
你是一个Facebook转发文案生成助手。

任务：为转发到小组生成文案。

原帖内容：
{post_content}

目标小组：{group_name}
行业：{industry}

要求：
1. 文案要自然、真诚
2. 避免过度营销
3. 符合小组氛围
4. 长度10-50字
5. 使用"分享"、"推荐"、"有用"等友好词汇
6. 返回JSON格式：{"caption": "文案内容", "length": 15}

请生成文案：
```

**文案示例：**
```
- 分享一个不错的内容
- 这个挺有用的，推荐给大家
- 看到这个觉得很有价值
- 分享给需要的朋友
- 这个内容值得一看
```

### 7.3 AI生成文案（动态）

**输入格式：**
```json
{
  "post_content": "原帖内容摘要",
  "caption_type": "timeline_share",
  "industry": "行业关键词"
}
```

**输出格式：**
```json
{
  "caption": "今天看到一个很有意思的内容，分享一下",
  "length": 22
}
```

**AI Prompt模板：**
```
你是一个Facebook动态文案生成助手。

任务：为转发到个人动态生成文案。

原帖内容：
{post_content}

行业：{industry}

要求：
1. 文案要个人化、自然
2. 可以加入个人感受
3. 避免过度营销
4. 长度10-80字
5. 使用第一人称"我"、"今天"等
6. 返回JSON格式：{"caption": "文案内容", "length": 22}

请生成文案：
```

**文案示例：**
```
- 今天看到一个很有意思的内容，分享一下
- 这个内容挺不错的，记录一下
- 学到了，分享给大家
- 觉得这个很有价值，转发
- 今天的收获，分享给朋友们
```

## 8. 数据库表结构

### posts_pool 表（待转发帖子池）
```
字段名              类型            说明
------------------- --------------- ---------------------------
id                  BIGINT          主键自增
post_url            VARCHAR(500)    帖子链接(唯一)
post_content        TEXT            帖子内容摘要
page_name           VARCHAR(200)    来源主页名称
page_url            VARCHAR(500)    来源主页链接
publish_time        TIMESTAMP       发布时间
likes_count         INT             点赞数
comments_count      INT             评论数
created_at          TIMESTAMP       创建时间

INDEX idx_url (post_url)
INDEX idx_page (page_url)
INDEX idx_time (publish_time)
```

### groups_pool 表（精准小组池）
```
字段名              类型            说明
------------------- --------------- ---------------------------
id                  BIGINT          主键自增
group_name          VARCHAR(200)    小组名称
group_url           VARCHAR(500)    小组链接(唯一)
group_members       INT             小组成员数
marketing_account   VARCHAR(100)    营销账号ID(NULL=未分配)
is_whitelist        TINYINT         是否白名单小组(0=否,1=是)
created_at          TIMESTAMP       创建时间
assigned_at         TIMESTAMP       分配时间
joined_at           TIMESTAMP       加入时间

INDEX idx_url (group_url)
INDEX idx_account (marketing_account)
INDEX idx_whitelist (is_whitelist)
```

**白名单说明：**
```
- is_whitelist=1：白名单小组（公共主页的官方小组）
- 白名单小组不能转发帖子到该小组
- 转发时自动过滤白名单小组
```

### account_share_round 表（账号转发轮次）
```
字段名              类型            说明
------------------- --------------- ---------------------------
id                  BIGINT          主键自增
account_id          VARCHAR(100)    账号ID(唯一)
round_number        INT             当前轮次编号
shared_groups       JSON            本轮已转发的小组名称列表
total_groups        INT             总小组数（30个）
round_progress      VARCHAR(20)     本轮进度（如"15/30"）
round_started_at    TIMESTAMP       本轮开始时间
round_completed_at  TIMESTAMP       本轮完成时间

INDEX idx_account (account_id)
INDEX idx_round (round_number)
```

**shared_groups JSON格式：**
```json
[
  "小组名称1",
  "小组名称2",
  "小组名称3"
]
```

**轮次管理逻辑：**
```
1. 每次转发成功后，将小组名称添加到shared_groups
2. 当shared_groups.length = total_groups时，本轮完成
3. 本轮完成后：
   - round_number + 1
   - shared_groups清空为[]
   - round_completed_at记录完成时间
   - round_started_at记录新轮次开始时间
4. 下次转发时，只选择不在shared_groups中的小组
```

### share_history 表（转发历史）
```
字段名              类型            说明
------------------- --------------- ---------------------------
id                  BIGINT          主键自增
account_id          VARCHAR(100)    账号ID
post_url            VARCHAR(500)    帖子链接
group_url           VARCHAR(500)    小组链接（可为NULL）
group_name          VARCHAR(200)    小组名称（可为NULL）
share_type          VARCHAR(50)     转发类型(group/story/timeline)
caption             TEXT            转发文案
share_time          TIMESTAMP       转发时间

INDEX idx_account (account_id)
INDEX idx_post (post_url)
INDEX idx_group (group_url)
INDEX idx_time (share_time)
INDEX idx_type (share_type)
```

**说明：**
- share_type=group时，group_url和group_name有值
- share_type=story或timeline时，group_url和group_name为NULL

## 9. 去重检查逻辑

```
检查项                         | 数据源           | 条件
-------------------------------|------------------|------------------
小组是否白名单                 | groups_pool表    | group_url = ? AND is_whitelist = 1
小组是否本轮已转发             | JSON文件         | shared_groups数组中是否存在group_url
今日是否已转发到动态           | JSON文件         | timeline_shared_today字段
今日是否已转发到快拍           | JSON文件         | story_shared_today字段
```

**去重规则：**
```
IF 小组是白名单:
    跳过该小组（不能转发到白名单小组）
ELSE IF 小组在JSON的shared_groups数组中:
    跳过该小组（本轮已转发）
ELSE IF 今日已转发到动态 AND 目标是动态:
    跳过动态转发（每天只转发一次）
ELSE:
    可以转发
```

**JSON文件完整结构：**
```json
{
  "account_id": "account_001",
  "current_round": 3,
  "round_start_time": "2024-01-15 10:00:00",
  "shared_groups": [
    {
      "group_url": "https://facebook.com/groups/xxx",
      "group_name": "小组名称1",
      "shared_at": "2024-01-15 10:05:00"
    }
  ],
  "total_groups": 30,
  "round_progress": "1/30",
  "round_completed": false,
  "timeline_shared_today": true,
  "timeline_shared_at": "2024-01-15 09:30:00",
  "story_shared_today": false,
  "story_shared_at": null,
  "last_updated": "2024-01-15 10:05:00"
}
```

## 10. 异常处理

```
异常类型             | 处理方式
---------------------|---------------------------
小组禁止转发         | 标记小组状态，跳过
白名单小组           | 自动过滤，不转发
转发失败             | 重试1次，失败则跳过
账号被限制           | 暂停24小时
```

## 11. API接口定义

### 检查帖子是否可转发

```
POST /api/check-post-available

请求：
{
  "post_url": "https://facebook.com/xxx/posts/xxx",
  "account_id": "account_001"
}

响应：
{
  "available": true,
  "reason": "可以转发",
  "in_pool": false,
  "in_excluded": false
}
```

### 提交帖子信息

```
POST /api/submit-post

请求：
{
  "post_url": "https://facebook.com/xxx/posts/xxx",
  "post_content": "帖子内容摘要",
  "page_name": "主页名称",
  "page_url": "主页链接",
  "publish_time": "2024-01-17 10:00:00",
  "likes_count": 120,
  "comments_count": 35
}

响应：
{
  "success": true,
  "post_id": 12345
}
```

### 批量添加到排除库

```
POST /api/add-posts-to-excluded

请求：
{
  "posts": [
    {
      "post_url": "https://facebook.com/xxx/posts/xxx",
      "post_content": "帖子内容摘要",
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

### 获取可转发小组列表

```
POST /api/get-available-groups

请求：
{
  "account_id": "account_001",
  "exclude_whitelist": true
}

响应：
{
  "success": true,
  "current_round": 3,
  "round_progress": "15/30",
  "groups": [
    {
      "group_url": "https://facebook.com/groups/xxx",
      "group_name": "小组名称",
      "members": 5000,
      "is_whitelist": 0,
      "shared_in_round": false
    }
  ]
}
```

**说明：**
- exclude_whitelist：是否排除白名单小组（默认true）
- shared_in_round：本轮是否已转发（从JSON文件读取）
- 只返回本轮未转发的小组

### 记录转发成功

```
POST /api/record-share-success

请求：
{
  "account_id": "account_001",
  "group_url": "https://facebook.com/groups/xxx",
  "group_name": "小组名称",
  "share_type": "group"
}

响应：
{
  "success": true,
  "current_round": 3,
  "round_progress": "16/30",
  "round_completed": false,
  "message": "已记录到JSON文件"
}
```

**说明：**
- 转发成功后调用此API
- 将小组添加到JSON文件的shared_groups数组
- 如果shared_groups.length = total_groups，则本轮完成
- 本轮完成后自动进入下一轮（清空shared_groups，round+1）

### 生成转发文案

```
POST /api/generate-caption

请求：
{
  "post_content": "帖子内容摘要",
  "group_name": "小组名称",
  "caption_type": "group_share",
  "industry": "行业关键词"
}

响应：
{
  "success": true,
  "caption": "分享一个不错的内容",
  "length": 10
}
```

**caption_type类型：**
```
- group_share: 转发到小组的文案
- timeline_share: 转发到动态的文案
- story_share: 转发到快拍的文案（通常不需要）
```

### 检查今日是否已转发到动态/快拍

```
POST /api/check-today-shared

请求：
{
  "account_id": "account_001",
  "share_type": "timeline"
}

响应：
{
  "success": true,
  "shared": false,
  "shared_at": null,
  "message": "今日未转发到动态"
}
```

**说明：**
- share_type: "timeline"（动态）或 "story"（快拍）
- shared: true=今日已转发，false=今日未转发
- 从JSON文件读取timeline_shared_today或story_shared_today字段

### 提交转发统计

```
POST /api/submit-share-stats

请求：
{
  "account_id": "account_001",
  "share_type": "group"
}

响应：
{
  "success": true,
  "message": "统计已提交"
}
```

**share_type类型：**
```
- group: 转发到小组
- story: 转发到快拍
- timeline: 转发到动态
```

**说明：**
- 只需要发送账号ID和转发类型
- 后端自动累加统计数据
- 用于数据面板显示

## 12. 执行流程伪代码

```javascript
// 获取账号阶段和配额
stage = getAccountStage(accountRegisterDate)
quota = getShareQuota(stage)

// 阶段1-3禁止转发
if (stage < 4) {
    console.log("当前阶段禁止转发")
    return
}

targetCount = random(quota.min, quota.max)

// 检查今日已转发数量
todayShared = getTodayShareCount(accountId)
if (todayShared >= quota.dailyMax) {
    console.log("今日配额已满")
    return
}

remainingQuota = quota.dailyMax - todayShared
targetCount = min(targetCount, remainingQuota)

console.log(`目标转发${targetCount}个帖子`)

sharedCount = 0
pageAttempts = 0
maxPageAttempts = 3

while (sharedCount < targetCount && pageAttempts < maxPageAttempts) {
    // 随机选择1-2个主页
    pages = getRandomPages(1, 2)
    
    for (page of pages) {
        console.log(`访问主页: ${page.name}`)
        
        // 打开主页
        openPage(page.url)
        sleep(random(2, 6))
        
        // 滚动获取帖子（最近30条）
        scrollTimes = random(5, 8)
        posts = []
        targetPostCount = 30
        
        for (i = 0; i < scrollTimes; i++) {
            newPosts = extractPostsFromPage()
            posts = posts.concat(newPosts)
            
            if (posts.length >= targetPostCount) {
                break
            }
            
            scrollDown()
            sleep(random(2, 5))
        }
        
        // 只保留最近30条
        posts = posts.slice(0, 30)
        
        console.log(`获取到${posts.length}个帖子`)
        
        // 过滤发布时间
        posts = posts.filter(p => p.publishTime <= 30天)
        console.log(`过滤后剩余${posts.length}个帖子`)
        
        // 数据库去重
        availablePosts = []
        for (post of posts) {
            checkResult = await checkPostAvailable(post.url, accountId)
            if (checkResult.available) {
                availablePosts.push(post)
            }
        }
        
        console.log(`去重后剩余${availablePosts.length}个帖子`)
        
        if (availablePosts.length === 0) {
            continue
        }
        
        // 随机打乱顺序（分散转发）
        shuffle(availablePosts)
        
        console.log(`随机选择帖子，200个账号会分散到不同帖子`)
        
        // 转发选中的帖子
        for (post of availablePosts) {
            if (sharedCount >= targetCount) break
            
            // 获取可转发的小组列表（本轮未转发的，排除白名单）
            groupsResult = await getAvailableGroups({
                account_id: accountId,
                post_url: post.url,
                limit: 10,
                exclude_whitelist: true
            })
            
            console.log(`当前轮次: ${groupsResult.current_round}`)
            console.log(`本轮进度: ${groupsResult.round_progress}`)
            console.log(`已过滤白名单小组`)
            
            if (groupsResult.groups.length === 0) {
                console.log(`本轮所有小组已转发完（或全是白名单），跳过帖子: ${post.url}`)
                continue
            }
            
            // 按权重随机选择1-3个小组
            targetGroupCount = random(1, 3)
            selectedGroups = weightedRandomSelect(groupsResult.groups, targetGroupCount)
            
            console.log(`选择${selectedGroups.length}个小组转发`)
            
            // 打开帖子
            clickPost(post.url)
            sleep(random(2, 6))
            
            // 阅读帖子（模拟真人）
            readTime = random(10, 30)
            console.log(`阅读帖子${readTime}秒`)
            sleep(readTime)
            
            // 概率点赞（80-100%）
            likeChance = random(80, 100)
            if (likeChance >= 80) {
                clickLike()
                console.log("点赞帖子")
                sleep(random(2, 5))
            }
            
            // 决定转发目标（独立概率判断）
            shareTargets = []
            
            // 100%转发到小组
            if (random(1, 100) <= 100) {
                shareTargets.push("groups")
            }
            
            // 50%转发到快拍
            if (random(1, 100) <= 50) {
                shareTargets.push("story")
            }
            
            // 60%转发到动态（检查今日是否已发）
            todayTimelineShared = await checkTodayTimelineShared(accountId)
            if (!todayTimelineShared && random(1, 100) <= 60) {
                shareTargets.push("timeline")
            } else if (todayTimelineShared) {
                console.log("今日已转发到动态，跳过")
            }
            
            // 随机打乱执行顺序
            shuffle(shareTargets)
            
            console.log(`转发目标: ${shareTargets.join(", ")}`)
            
            // 按随机顺序执行转发
            for (target of shareTargets) {
                if (target === "groups") {
                    await shareToGroups(accountId, post)
                } else if (target === "story") {
                    await shareToStory(accountId, post)
                } else if (target === "timeline") {
                    await shareToTimeline(accountId, post)
                }
                
                // 转发下一个目标间隔
                if (shareTargets.indexOf(target) < shareTargets.length - 1) {
                    interval = random(10, 20)
                    console.log(`等待${interval}秒后转发到下一个目标`)
                    sleep(interval)
                }
            }
            
            sharedCount++
                        group_name: group.group_name,
                        caption_type: captionType,
                        industry: "行业关键词"
                    })
                    
                    caption = captionResult.caption
                    
                    // 输入文案
                    typeCaption(caption)
                    sleep(random(3, 8))
                }
                
                // 点击发布
                clickPublish()
                sleep(random(2, 5))
                
                // 等待发布完成
                sleep(random(3, 8))
                
                // 记录转发历史
                shareResult = await recordShare({
                    account_id: accountId,
                    post_url: post.url,
                    group_url: group.group_url,
                    group_name: group.group_name,
                    caption: caption
                })
                
                console.log(`成功转发到小组: ${group.group_name}`)
                console.log(`本轮进度: ${shareResult.round_progress}`)
                
                if (shareResult.round_completed) {
                    console.log(`本轮所有小组已转发完成，进入下一轮: ${shareResult.round_number}`)
                }
                
                sharedCount++
                
                // 转发下一个小组间隔（同一帖子）
                if (selectedGroups.indexOf(group) < selectedGroups.length - 1) {
                    interval = random(15, 30)
                    console.log(`等待${interval}秒后转发到下一个小组`)
                    sleep(interval)
                }
            }
            
            // 返回主页
            goBackToPage()
            sleep(random(2, 6))
            
            // 选择下一个帖子间隔
            if (sharedCount < targetCount) {
                interval = random(5, 15)
                console.log(`等待${interval}秒后选择下一个帖子`)
                sleep(interval)
            }
        }
    }
    
    pageAttempts++
}

console.log(`完成，共转发${sharedCount}个帖子`)

// 选择访问方式
function selectAccessMethod(stage) {
    if (stage < 3) {
        return "direct_link" // 阶段1-2只能直接访问
    }
    
    methods = []
    weights = []
    
    // 直接链接（全阶段）
    methods.push("direct_link")
    weights.push(40)
    
    // 搜索主页（阶段3+）
    if (stage >= 3) {
        methods.push("search")
        weights.push(30)
    }
    
    // 从动态进入（阶段4+）
    if (stage >= 4) {
        methods.push("from_timeline")
        weights.push(20)
    }
    
    // 从首页进入（阶段5+）
    if (stage >= 5) {
        methods.push("from_feed")
        weights.push(10)
    }
    
    return weightedRandomSelectOne(methods, weights)
}

// 决定转发目标（已废弃，改为独立概率判断）
// function decideShareTarget() {
//     rand = random(1, 100)
//     if (rand <= 70) return "groups"
//     if (rand <= 85) return "story"
//     return "timeline"
// }

// 转发到小组
async function shareToGroups(accountId, post) {
    // 获取可转发的小组列表（本轮未转发的，排除白名单）
    groupsResult = await getAvailableGroups({
        account_id: accountId,
        limit: 10,
        exclude_whitelist: true
    })
    
    console.log(`当前轮次: ${groupsResult.current_round}`)
    console.log(`本轮进度: ${groupsResult.round_progress}`)
    console.log(`本轮已转发: ${groupsResult.shared_groups.join(", ")}`)
    
    if (groupsResult.groups.length === 0) {
        console.log(`本轮所有小组已转发完，跳过`)
        return
    }
    
    // 选择1-3个小组
    targetGroupCount = random(1, 3)
    selectedGroups = weightedRandomSelect(groupsResult.groups, targetGroupCount)
    
    console.log(`选择${selectedGroups.length}个小组转发`)
    
    // 转发到每个小组
    for (group of selectedGroups) {
        console.log(`转发到小组: ${group.group_name}`)
        
        clickShareButton()
        sleep(random(2, 5))
        
        clickShareToGroup()
        sleep(random(2, 4))
        
        selectGroup(group.group_url)
        sleep(random(2, 4))
        
        // AI生成文案（必须）
        console.log("AI生成转发文案...")
        captionResult = await generateCaption({
            post_content: post.content,
            group_name: group.group_name,
            caption_type: "group_share",
            industry: "行业关键词"
        })
        
        caption = captionResult.caption
        
        // 输入文案
        typeCaption(caption)
        sleep(random(3, 8))
        
        clickPublish()
        sleep(random(2, 5))
        sleep(random(3, 8))
        
        // 记录转发历史
        shareResult = await recordShare({
            account_id: accountId,
            post_url: post.url,
            group_url: group.group_url,
            group_name: group.group_name,
            caption: caption,
            share_type: "group"
        })
        
        // 提交统计数据
        await submitShareStats({
            account_id: accountId,
            share_type: "group"
        })
        
        console.log(`成功转发到小组: ${group.group_name}`)
        console.log(`本轮进度: ${shareResult.round_progress}`)
        
        if (shareResult.round_completed) {
            console.log(`✓ 本轮所有小组已转发完成！`)
            console.log(`✓ 自动进入下一轮: 第${shareResult.round_number}轮`)
            console.log(`✓ 已转发小组列表已清空，重新开始`)
        }
        
        sharedCount++
        
        // 转发下一个小组间隔
        if (selectedGroups.indexOf(group) < selectedGroups.length - 1) {
            interval = random(15, 30)
            sleep(interval)
        }
    }
}

// 转发到快拍
async function shareToStory(accountId, post) {
    console.log("转发到快拍")
    
    clickShareButton()
    sleep(random(2, 5))
    
    clickShareToStory()
    sleep(random(2, 4))
    
    // 快拍通常不添加文案，直接发布
    clickPublish()
    sleep(random(2, 5))
    sleep(random(3, 8))
    
    // 记录转发历史
    await recordShare({
        account_id: accountId,
        post_url: post.url,
        share_type: "story"
    })
    
    // 提交统计数据
    await submitShareStats({
        account_id: accountId,
        share_type: "story"
    })
    
    console.log("成功转发到快拍")
}

// 转发到动态
async function shareToTimeline(accountId, post) {
    console.log("转发到动态")
    
    clickShareButton()
    sleep(random(2, 5))
    
    clickShareToTimeline()
    sleep(random(2, 4))
    
    // AI生成文案（必须）
    console.log("AI生成动态文案...")
    captionResult = await generateCaption({
        post_content: post.content,
        caption_type: "timeline_share",
        industry: "行业关键词"
    })
    
    caption = captionResult.caption
    
    // 输入文案
    typeCaption(caption)
    sleep(random(3, 8))
    
    clickPublish()
    sleep(random(2, 5))
    sleep(random(3, 8))
    
    // 记录转发历史
    await recordShare({
        account_id: accountId,
        post_url: post.url,
        share_type: "timeline",
        caption: caption
    })
    
    // 提交统计数据
    await submitShareStats({
        account_id: accountId,
        share_type: "timeline"
    })
    
    console.log("成功转发到动态")
}

// 决定文案类型
function decideCaptionType() {
    rand = random(1, 100)
    if (rand <= 40) return "no_caption"
    if (rand <= 75) return "simple_intro"
    if (rand <= 90) return "personal_view"
    return "question"
}

// 按权重随机选择
function weightedRandomSelect(groups, count) {
    // 构建权重数组
    weightedArray = []
    for (group of groups) {
        weight = group.weight
        for (i = 0; i < weight; i++) {
            weightedArray.push(group)
        }
    }
    
    // 洗牌算法
    shuffle(weightedArray)
    
    // 去重选择
    selected = []
    for (item of weightedArray) {
        if (!selected.includes(item)) {
            selected.push(item)
        }
        if (selected.length >= count) break
    }
    
    return selected
}
```

## 13. 关键优化点

### 风控友好设计

1. **渐进式配额**
   - 阶段1-3：禁止转发（0个）
   - 阶段4：1-2个帖子/次
   - 阶段6：3-5个帖子/次

2. **转发间隔**
   - 同一帖子转发不同小组：15-30秒
   - 不同帖子之间：30-90秒
   - 单次任务总时长：3-15分钟

3. **小组冷却机制**
   - 同一小组24小时内只转发1次
   - 避免频繁刷屏

4. **文案多样化**
   - 40%不添加文案
   - 60%添加不同类型文案
   - AI生成自然文案

5. **AI判断后永久保存**
   - 符合的帖子保存到待转发池
   - 不符合的帖子保存到排除库
   - 避免重复AI分析

6. **小组权重选择**
   - 优先选择长时间未转发的小组
   - 大小组获得更高权重
   - 避免固定顺序

7. **行为自然化**
   - 访问主页，滚动获取最近30条帖子
   - 随机选择一条帖子
   - 阅读帖子10-30秒（模拟真人）
   - 80-100%概率点赞
   - 点赞后再转发
   - 每个转发目标独立判断概率
   - 执行顺序随机，避免固定模式

8. **分散转发策略**
   - 每个账号获取最近30条帖子
   - 200个账号分散到30条 = 每条约7个账号
   - 滚动5-8次即可完成（1-2分钟）
   - 时间成本低，风控效果好

9. **白名单小组过滤**
   - 公共主页的官方小组设为白名单
   - 白名单小组不能转发帖子
   - 转发时自动过滤白名单小组
   - 避免在官方小组刷屏

