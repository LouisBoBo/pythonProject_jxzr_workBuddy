<h1 align="center">数据库结构参考说明文档</h1>

> 本文档根据数据字典生成，为使用人员提供数据库表结构参考，帮助快速熟悉表定义及字段含义

## 变更记录

| 序号 | 变更内容 | 变更时间 | 变更人 | 备注 |
|------|----------|----------|--------|------|
| 1 | V1.6 | 待填写 | 自动生成脚本 | 初始版本 |
|  |  |  |  |  |

## 一、文档概述

### 1.1 文档目的

本文档旨在为使用人员提供数据库结构的全面参考，使使用人员能够：
- 快速理解各数据表的用途及字段含义
- 掌握各表所属业务域与数据库来源
- 准确编写查询语句进行数据提取
- 快速完成系统数据字典查阅

---

## 二、核心数据表结构

### 2.1 系统信息

> 本章节数据来源于 Excel 工作表：`系统信息`

#### 1 数据字典 ( TBL_SYS_DICTIONARY )
- **业务含义**：描述了大部分字符串常量对应的中文含义
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CCODE_PATH | string | 是 | - | 字典描述 |
| CDIC_CODE | string | 是 | - | 字典代码 |
| CDIC_DESC | string | 是 | - | 字典描述 |
| CDIC_GROUP_VALUE_EXPRESSION | string | 是 | - | 字典值表达式 |
| CDIC_GROUP_VALUE_TYPE | string | 是 | - | 字典值类型 |
| CDIC_NAME | string | 是 | - | 字典名称 |
| CDIC_TYPE | string | 是 | - | 字典类型 |
| CDIC_VALUE | string | 是 | - | 字典值 |
| CDIC_VALUE_EX | string | 是 | - | 字典值扩展 |
| CIS_CATEGORY | string | 是 | - | 是否系统级 |
| CIS_DEFAULT | string | 是 | - | 是否默认 |
| CIS_SYS | string | 是 | - | 是否系统级 |
| CNAME_PATH | string | 是 | - | 字典描述 |
| CPARENT | string | 是 | - | 父字典名称 |
| CPARENT_DIC_ID | long | 否 | - | 父字典ID，对应TBL_SYS_DICTIONARY.CID |
| CSEQ | int? | 是 | - | 字典在分组中的顺序 |
| CID | long | 否 | - | 主键 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_SYS_DICTIONARY.CPARENT_DIC_ID = TBL_SYS_DICTIONARY.CID

---

#### 2 组织机构表 ( TBL_SYS_ORGANIZATION )
- **业务含义**：描述系统中包含的组织信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CORG_NAME | string | 是 | - | 组织名称 |
| CORG_NO | string | 是 | - | 组织编码 |
| CPARENT_ORG_ID | long? | 是 | - | 上级组织ID，对应TBL_SYS_ORGANIZATION.CID |
| CID | long | 否 | - | 主键 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_SYS_ORGANIZATION.CPARENT_ORG_ID = TBL_SYS_ORGANIZATION.CID
  - TBL_SYS_USER_ORG_MAP.CORG_ID = TBL_SYS_ORGANIZATION.CID
  - TBL_SYS_USER.CORG_CODE = TBL_SYS_ORGANIZATION.CID

---

#### 3 系统参数配置表 ( TBL_SYS_PARAM )
- **业务含义**：描述系统中各种基础运行插件参数
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CIS_SYS | string | 是 | - | 是否系统级 |
| CPARAM_CODE | string | 是 | - | 参数编码 |
| CPARAM_DESC | string | 是 | - | 参数描述 |
| CPARAM_NAME | string | 是 | - | 参数名称 |
| CPARAM_TYPE | long? | 是 | - | 参数分类ID，对应TBL_SYS_PARAM_TYPE.CID |
| CPARAM_VALUE | string | 是 | - | 参数值 |
| CPARAM_VALUE_EXPR | string | 是 | - | 参数校验表达式(正规则表达式，用于检验) |
| CPARAM_VALUE_EXT | string | 是 | - | 参数扩展值 |
| CPARAM_VALUE_SHOW_TYPE | string | 是 | - | 参数值显示类型(下拉框、文本框、复选框等) |
| CPARAM_VALUE_SOURCE | string | 是 | - | 参数值来源 |
| CPARAM_VALUE_TYPE | string | 是 | - | 参数值类型(来自于数据字典(用于值转换):整型、字符串、BOOL、FLOAT) |
| CREMARK | string | 是 | - | 备注信息 |
| CSEQ | int? | 是 | - | 参数在分组中的顺序 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_SYS_PARAM.CPARAM_TYPE = TBL_SYS_PARAM_TYPE.CID

---

#### 4 系统参数分类表 ( TBL_SYS_PARAM_TYPE )
- **业务含义**：描述系统参数的分类类型
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CPARAM_TYPE_DESC | string | 是 | - | 类别描述 |
| CPARAM_TYPE_NAME | string | 是 | - | 类别名称 |
| CPARAM_TYPE_NO | string | 是 | - | 类别代码 |
| CPARAM_TYPE_PATH | string | 是 | - | 类别路径 |
| CPARENT_ID | long | 否 | - | 上级分类，对应TBL_SYS_PARAM_TYPE.CID |
| CREMARK | string | 是 | - | 备注 |
| CSEQ | int? | 是 | - | 父级下的顺序号 |
| CID | long | 否 | - | 主键 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_SYS_PARAM_TYPE.CPARENT_ID = TBL_SYS_PARAM_TYPE.CID

---

#### 5 系统角色表 ( TBL_SYS_ROLE )
- **业务含义**：描述系统用户角色列表
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CROLE_CODE | string | 是 | - | 角色编码 |
| CROLE_NAME | string | 是 | - | 角色名称 |
| CID | long | 否 | - | 主键 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_SYS_USER_ROLE_MAP.CROLE_ID = TBL_SYS_ROLE.CID

---

#### 6 系统服务配置表 ( TBL_SYS_SERVER )
- **业务含义**：描述系统各服务配置信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CSERVICE_NAME | string | 是 | - | 服务名称 |
| CSERVICE_NO | string | 是 | - | 服务编码 |
| CSERVICE_PASSWORD | string | 是 | - | 服务密码 |
| CSERVICE_PATH | string | 是 | - | 服务地址 |
| CSERVICE_USER | string | 是 | - | 服务账号 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：无

---

#### 7 系统模板配置表 ( TBL_SYS_TEMPLATE_CONFIG )
- **业务含义**：描述系统配置文件模板功能的相关数据
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CBINDING | string | 是 | - | Excel单元格绑定数据源信息序列化后的json字符串 |
| CBUCKET_NAME | string | 是 | - | 模板文件MinIO桶名称 |
| CCODE | string | 是 | - | 模板编码 |
| CDATA | string | 是 | - | 绑定数据源列表序列化后的json字符串 |
| CDESC | string | 是 | - | 模板描述 |
| CFILE_NAME | string | 是 | - | 上传的模板文件名称 |
| CFILE_PATH | string | 是 | - | 模板文件MinIO路径 |
| CNAME | string | 是 | - | 模板名称 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：无

---

#### 8 系统用户表 ( TBL_SYS_USER )
- **业务含义**：描述所有的系统用户信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CCUR_HOST | string | 是 | - | 当前登录主机 |
| CDATETIME_LAST_LOCKED_OUT | DateTime | 否 | - | 最后锁定时间 |
| CDATETIME_LAST_LOGIN | DateTime | 否 | - | 最后登录时间 |
| CDEFAULT_HOST | string | 是 | - | 默认登录主机 |
| CDISPLAY_NAME | string | 是 | - | 用户显示名 |
| CEMAIL | string | 是 | - | 邮箱 |
| CFAILED_ATTEMPT_COUNT | int | 否 | - | 登录失败次数 |
| CFAILED_ATTEMPT_START | DateTime | 否 | - | 失败计数开始时间 |
| CGENDER | string | 是 | - | 性别 |
| CIS_LOCKED_OUT | string | 是 | - | 是否锁定 |
| CIS_ONLINE | string | 是 | - | 是否在线 |
| CMOBILEPHONE | string | 是 | - | 手机号 |
| CORG_CODE | long | 否 | - | 组织编号 |
| CPASSWORD | string | 是 | - | 密码 |
| CUSER_NAME | string | 是 | - | 用户账号 |
| CUSER_TYPE | string | 是 | - | 用户类型 |
| CID | long | 否 | - | 主键 |
| CSTATE | string | 是 | - | 状态标识 |
- **关联关系**：
  - TBL_SYS_USER.CORG_CODE = TBL_SYS_ORGANIZATION.CID
  - TBL_SYS_USER_ORG_MAP.CUSER_ID = TBL_SYS_USER.CID
  - TBL_SYS_USER_ROLE_MAP.CUSER_ID = TBL_SYS_USER.CID
  - TBL_MSG_GROUP_USER.CUSER_ID = TBL_SYS_USER.CID
  - TBL_MSG_USER.CUSER_ID = TBL_SYS_USER.CID
  - TBL_QM_ASSAY_LOG.CASSAY_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_QM_ASSAY_LOG.CCHECK_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_QM_ASSAY_LOG.CRECEIVE_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_QM_ASSAY_LOG.CSAMPLE_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_QM_ASSAY_LOG_ITEM.CRETEST_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_QM_CC_EXCEPTION.CAUDIT_MAN = TBL_SYS_USER.CUSER_NAME
  - TBL_QM_CC_EXCEPTION.CCHECK_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_QM_CC_EXCEPTION.CRECEIVE_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_QM_COMPLAINT.CRESPONSIBLE_PERSON = TBL_SYS_USER.CUSER_NAME
  - TBL_QM_INSPECT_RECORD.CCHECK_USER_NAME = TBL_SYS_USER.CUSER_NAME
  - TBL_QM_INSPECT_RECORD.CINSPECT_USER_NAME = TBL_SYS_USER.CUSER_NAME
  - TBL_QM_INSPECT_RECORD.CLAB_INSPECT_USER_NAME = TBL_SYS_USER.CUSER_NAME
  - TBL_QM_INSPECT_RECORD.CLAB_RECEIVE_USER_NAME = TBL_SYS_USER.CUSER_NAME
  - TBL_QM_PL_LOG.CCHECK_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_QM_PL_LOG.CINSPECT_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_QM_PL_LOG.CRECEIVE_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_QM_PL_LOG.CSUBMIT_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_ESOP_CONTACT_FORM.CAPPROVAL_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_ESOP_CONTACT_FORM.CISSUE_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_ESOP_CONTACT_FORM.CREVIEW_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_ESOP_COUNTERSIGN.CUSER_NAME = TBL_SYS_USER.CUSER_NAME
  - TBL_ESOP_FILE.CAUDIT_MAN = TBL_SYS_USER.CUSER_NAME
  - TBL_ESOP_FILE.CSCRAP_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_ESOP_TEMPORARY_CHANGE_ORDER.CAPPLICANT_NAME = TBL_SYS_USER.CUSER_NAME
  - TBL_ESOP_TEMPORARY_CHANGE_ORDER.CCONFIRM_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_ESOP_TEMPORARY_CHANGE_ORDER.CREVIEW_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_NP_TEMPLATE_CHANGE.CAUDIT_USER_ID = TBL_SYS_USER.CUSER_NAME
  - TBL_NP_TEMPLATE_CHANGE.CCHANGE_USER_ID = TBL_SYS_USER.CUSER_NAME
  - TBL_EAM_MAINTAIN_TASK.CEMPOLYEE_NO = TBL_SYS_USER.CUSER_NAME
  - TBL_EAM_REPAIR.CAPPLY_MAN = TBL_SYS_USER.CUSER_NAME
  - TBL_EAM_REPAIR.CASSIGNMENT_MAN = TBL_SYS_USER.CUSER_NAME
  - TBL_EAM_REPAIR.CAUDIT_USERNAME = TBL_SYS_USER.CUSER_NAME
  - TBL_EAM_REPAIR.CCLOSE_MAN = TBL_SYS_USER.CUSER_NAME
  - TBL_EAM_REPAIR.CODE = TBL_SYS_USER.CUSER_NAME
  - TBL_EAM_REPAIR.CREPAIR_MAN = TBL_SYS_USER.CUSER_NAME
  - TBL_EAM_REPAIR_MAN.CREPAIR_MAN_CODE_PRE = TBL_SYS_USER.CUSER_NAME
  - TBL_SFC_DBFC_USER.CUSER_NAME = TBL_SYS_USER.CUSER_NAME
  - TBL_SFC_WS_LOG.CCHECK_USER_NAME = TBL_SYS_USER.CUSER_NAME
  - TBL_SFC_WS_LOG.CEND_USER_NAME = TBL_SYS_USER.CUSER_NAME
  - TBL_SFC_WS_LOG.CSTART_USER_NAME = TBL_SYS_USER.CUSER_NAME
  - TBL_WMS_PICKING_LOG.CUSER_NAME = TBL_SYS_USER.CUSER_NAME
  - TBL_WMS_BARCODE_SPLIT_RECORD.CSPLIT_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_SRM_RECEIVING.CRECEIVING_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_SRM_RECEIVING_DTL.CINSPECT_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_OQC_SHIPMENT_GENERATE.CGENERATE_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_OQC_SHIPMENT_GENERATE_LOG.CAUDIT_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_OQC_SHIPMENT_GENERATE_LOG.CGENERATE_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_FA_TXDD_MAIN.CAUDIT_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_FA_TXDD_MAIN.CCREATOR = TBL_SYS_USER.CUSER_NAME
  - TBL_FA_TXDD_MAIN.CINSPECT_DDCS = TBL_SYS_USER.CUSER_NAME
  - TBL_FA_TXDD_MAIN.CINSPECT_GBFS = TBL_SYS_USER.CUSER_NAME
  - TBL_FA_TXDD_MAIN.CINSPECT_KTHD = TBL_SYS_USER.CUSER_NAME
  - TBL_FA_TXDD_MAIN.CINSPECT_QPBT = TBL_SYS_USER.CUSER_NAME
  - TBL_FA_TXDD_MAIN.CINSPECT_SKKJ = TBL_SYS_USER.CUSER_NAME
  - TBL_FA_TXDD_MAIN.CINSPECT_SKXK = TBL_SYS_USER.CUSER_NAME
  - TBL_FA_TXDD_MAIN.CINSPECT_ZKCS = TBL_SYS_USER.CUSER_NAME
  - TBL_FA_TXDD_QPBT.CINSPECT_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_FA_YHYJ_MAIN.CAUDIT_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_FA_YHYJ_MAIN.CCREATOR1 = TBL_SYS_USER.CUSER_NAME
  - TBL_FA_YHYJ_MAIN.CCREATOR2 = TBL_SYS_USER.CUSER_NAME
  - TBL_FA_YHYJ_MAIN.CCREATOR3 = TBL_SYS_USER.CUSER_NAME
  - TBL_MEP_MATERIAL_PARAM.CCONFIRMED_USER = TBL_SYS_USER.CUSER_NAME

---

#### 9 用户组织关系 ( TBL_SYS_USER_ORG_MAP )
- **业务含义**：描述了用户与组织关联的信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CIS_DEFAULT | string | 是 | - | 是否默认组织 |
| CIS_DEPT_MANAGER | string | 是 | - | 是否部门负责人 |
| CORG_ID | long | 否 | - | 组织ID，对应TBL_SYS_ORGANIZATION.CID |
| CUSER_ID | long | 否 | - | 用户ID，对应TBL_SYS_USER.CID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_SYS_USER_ORG_MAP.CUSER_ID = TBL_SYS_USER.CID
  - TBL_SYS_USER_ORG_MAP.CORG_ID = TBL_SYS_ORGANIZATION.CID

---

#### 10 用户角色关系表 ( TBL_SYS_USER_ROLE_MAP )
- **业务含义**：描述了用户与角色关联的信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CROLE_ID | long | 否 | - | 角色ID，对应TBL_SYS_ROLE.CID |
| CUSER_ID | long | 否 | - | 用户ID，对应TBL_SYS_USER.CID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_SYS_USER_ROLE_MAP.CUSER_ID = TBL_SYS_USER.CID
  - TBL_SYS_USER_ROLE_MAP.CROLE_ID = TBL_SYS_ROLE.CID

---

### 2.2 基础数据

> 本章节数据来源于 Excel 工作表：`基础数据`

#### 11 客户信息表 ( TBL_BD_CUSTOMER )
- **业务含义**：维护工厂的所有的客户信息，包括客户编号和客户名称等
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CUSTOMER_NAME | string | 是 | - | 客户名称 |
| CUSTOMER_NO | string | 是 | - | 客户编号 |
| CID | long | 否 | - | 主键ID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_BD_CUSTOMER.CUSTOMER_NO = TBL_BD_ITEM.CUSTOMER_CODE
  - TBL_BD_CUSTOMER.CID = TBL_SFC_PACKAGE_LABEL_LINK.CCUSTOMER_ID
  - TBL_BD_CUSTOMER.CID = TBL_SFC_PACKAGE_RULE_LINK.CCUSTOMER_ID
  - TBL_BD_CUSTOMER.CUSTOMER_NO = TBL_QM_INSPECT_RECORD.CUSTOMER_CODE
  - TBL_BD_CUSTOMER.CUSTOMER_NO = TBL_QM_PL_LOG.CUSTOMER_CODE

---

#### 12 产品和物料信息表 ( TBL_BD_ITEM )
- **业务含义**：包含了工厂中所有生产产品、原材料物料的信息，信息从ERP系统同步而来
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CBOX_QTY | decimal? | 是 | - | 每箱标准数 |
| CCUSTOMER_MATER_NAME | string | 是 | - | 客户物料名称 |
| CCUSTOMER_MATER_NO | string | 是 | - | 客户物料编号 |
| CCUSTOMER_MATERIAL | string | 是 | - | 客户材料 |
| CCUSTOMER_MODEL | string | 是 | - | 客户型号 |
| CHEIGHT | decimal? | 是 | - | 高度 |
| CITEM_DESC | string | 是 | - | 产品描述 |
| CITEM_NAME | string | 是 | - | 产品名称 |
| CITEM_NO | string | 是 | - | 产品编号 |
| CITEM_SOURCE | string | 是 | - | 产品来源 |
| CITEM_SPEC | string | 是 | - | 产品规格 |
| CITEM_TYPE_ID | long? | 是 | - | 产品类型ID，对应TBL_BD_ITEM_TYPE.CID |
| CITEM_VERSION | string | 是 | - | 产品版本 |
| CITEM_WEIGHT | decimal? | 是 | - | 产品单重 |
| CLEN | decimal? | 是 | - | 长度 |
| CPACKAGE_QTY | decimal? | 是 | - | 单包数量 |
| CPLATE_WEIGHT | decimal? | 是 | - | 隔板重量 |
| CROUTE_ID | string | 是 | - | 工艺路线ID |
| CTYPE | string? | 是 | - | 类型，Merger：合拼；Sample：样本；Batch：批量生产 |
| CUSTOMER_CODE | string | 是 | - | 客户代码 |
| CWIDTH | decimal? | 是 | - | 宽度 |
| CID | long | 否 | - | 主键ID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_BD_ITEM.CITEM_TYPE_ID = TBL_BD_ITEM_TYPE.CID
  - TBL_BD_ITEM.CITEM_NO = TBL_BD_PROCESS_OUTS.CPRODUCT_ITEM_NO
  - TBL_BD_ITEM.CITEM_NO = TBL_EAP_ALARM.CITEM_NO
  - TBL_BD_ITEM.CITEM_NO = TBL_EAP_AOI_DETECTIONS.CMAP_ITEM_NO
  - TBL_BD_ITEM.CITEM_NO = TBL_EAP_BT_PARAM.CITEM_NO
  - TBL_BD_ITEM.CITEM_NO = TBL_EAP_GE_PARAM.CITEM_NO
  - TBL_BD_ITEM.CITEM_NO = TBL_EAP_HONGSHENG_RECORDS.CITEM_NO
  - TBL_BD_ITEM.CITEM_NO = TBL_EAP_LDI_LOG.CITEM_NO
  - TBL_BD_ITEM.CITEM_NO = TBL_EAP_LDI_PARAM.CITEM_NO
  - TBL_BD_ITEM.CITEM_NO = TBL_EAP_MASON_DETECTIONS_DTL.CITEM_NO
  - TBL_BD_ITEM.CITEM_NO = TBL_EAP_PATTERN_PLAT.CITEM_NO
  - TBL_BD_ITEM.CITEM_NO = TBL_EAP_PMS_CONTENT.CITEM_NO
  - TBL_BD_ITEM.CITEM_NO = TBL_EAP_YUHUI_TEST_RECORDS.CITEM_NO
  - TBL_BD_ITEM.CID = TBL_QM_CC_EXCEPTION.CITEM_ID
  - TBL_BD_ITEM.CID = TBL_QM_INSPECT_RECORD.CITEM_ID
  - TBL_BD_ITEM.CID = TBL_QM_PL_LOG.CITEM_ID
  - TBL_BD_ITEM.CID = TBL_SFC_PACKAGE.CITEM_ID
  - TBL_BD_ITEM.CID = TBL_SFC_PACKAGE_LABEL_LINK.CITEM_ID
  - TBL_BD_ITEM.CID = TBL_SFC_PACKAGE_RULE_LINK.CITEM_ID
  - TBL_BD_ITEM.CID = TBL_SFC_RECIPE_PRODUCT.CITEM_ID
  - TBL_BD_ITEM.CID = TBL_SFC_WS_LOG.CITEM_ID
  - TBL_BD_ITEM.CID = TBL_MO.CITEM_ID
  - TBL_BD_ITEM.CITEM_NO = TBL_MO_OUTS.CITEM_NO
  - TBL_BD_ITEM.CITEM_NO = TBL_SRM_PO_DELIVERY.CITEM_CODE
  - TBL_BD_ITEM.CITEM_NO = TBL_SRM_PO_DETAIL.CITEM_CODE
  - TBL_BD_ITEM.CITEM_NO = TBL_SRM_RECEIVING_DTL.CITEM_CODE
  - TBL_BD_ITEM.CITEM_NO = TBL_SPC_CONTROL_CHARACTERISTIC_ITEM_LINK.CITEM_NO
  - TBL_BD_ITEM.CITEM_NO = TBL_OQC_SHIPMENT_ITEM_LINK.CITEM_ID
  - TBL_BD_ITEM.CITEM_NO = TBL_OQC_SHIPMENT_GENERATE.CITEM_NO
  - TBL_BD_ITEM.CITEM_NO = TBL_FA_TXDD_MAIN.CITEM_NO
  - TBL_BD_ITEM.CITEM_NO = TBL_FA_YHYJ_MAIN.CITEM_NO
  - TBL_BD_ITEM.CID = TBL_MEP_MATERIAL_PARAM.CITEM_ID

---

#### 13 产品和物料类型表 ( TBL_BD_ITEM_TYPE )
- **业务含义**：描述了TBL_BD_ITEM表中的生产产品、物料可对应的类型
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CITEM_CONTROL_TYPE | long? | 是 | - | 物料管控类型 |
| CITEM_TYPE_BARCODE | string | 是 | - | 物料类型条码 |
| CITEM_TYPE_NAME | string | 是 | - | 物料类型名称 |
| CITEM_TYPE_NO | string | 是 | - | 物料类型编码 |
| CITEM_TYPE_PATH | string | 是 | - | 类型层级路径 |
| CPARENT_TYPE_ID | long? | 是 | - | 上级类型ID，对应TBL_BD_ITEM_TYPE.CID |
| CREMARK | string | 是 | - | 备注 |
| CSEQ | int | 否 | - | 排序号 |
| CSOURCE_ID | string | 是 | - | 来源系统ID |
| CID | long | 否 | - | 主键ID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_BD_ITEM_TYPE.CID = TBL_BD_ITEM.CITEM_TYPE_ID
  - TBL_BD_ITEM_TYPE.CPARENT_TYPE_ID = TBL_BD_ITEM_TYPE.CID
  - TBL_BD_ITEM_TYPE.CID = TBL_BD_WC_ITEMTYPE_LINK.CITEM_TYPE_ID

---

#### 14 工序工艺信息表 ( TBL_BD_PROCESS )
- **业务含义**：包含了工厂中的所有的生产工序信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CIS_COUNT | string | 是 | - | 是否计数工序 |
| CPARENT_PROCESS_ID | long? | 是 | - | 上级工序ID，对应TBL_BD_PROCESS.CID |
| CPROCESS_CONTROL_TYPE | long? | 是 | - | 工序管控类型 |
| CPROCESS_DESC | string | 是 | - | 工序描述 |
| CPROCESS_NAME | string | 是 | - | 工序名称 |
| CPROCESS_NO | string | 是 | - | 工序编码 |
| CPROCESS_PATH | string | 是 | - | 工序路径 |
| CPROCESS_SEQ | int? | 是 | - | 工序顺序 |
| CPROCESS_SHORT_CODE | string | 是 | - | 工序简称 |
| CPROCESS_TYPE_ID | long? | 是 | - | 工序类型ID |
| CREMARK | string | 是 | - | 备注 |
| CSOURCE_ID | string | 是 | - | 来源系统ID |
| CID | long | 否 | - | 主键ID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_BD_PROCESS.CPARENT_PROCESS_ID = TBL_BD_PROCESS.CID
  - TBL_BD_PROCESS.CID = TBL_BD_PROCESS_OUTS.CPROCESS_ID
  - TBL_BD_PROCESS.CPROCESS_NO = TBL_EAP_BT_PARAM.CPROCESS
  - TBL_BD_PROCESS.CID = TBL_BD_WC_PROCESS_LINK.CPROCESS_ID
  - TBL_BD_PROCESS.CID = TBL_QM_CC_EXCEPTION.CDUTY_PROCESS_ID
  - TBL_BD_PROCESS.CID = TBL_QM_CC_EXCEPTION.CEXCEP_PROCESS_ID
  - TBL_BD_PROCESS.CID = TBL_QM_CC_EXCEPTION.COUT_PROCESS_ID
  - TBL_BD_PROCESS.CPROCESS_NAME = TBL_QM_COMPLAINT.COCCURRENCE_PROCESS
  - TBL_BD_PROCESS.CPROCESS_NAME = TBL_QM_COMPLAINT.COUTFLOW_PROCESS
  - TBL_BD_PROCESS.CID = TBL_QM_INSPECT_RECORD.CPROCESS_ID
  - TBL_BD_PROCESS.CID = TBL_QM_PL_LOG.CPROCESS_ID
  - TBL_BD_PROCESS.CID = TBL_SFC_RECIPE_LOT.CPROCESS_ID
  - TBL_BD_PROCESS.CID = TBL_SFC_RECIPE_PRODUCT.CPROCESS_ID
  - TBL_BD_PROCESS.CID = TBL_SFC_WS_LOG.CPROCESS_ID
  - TBL_BD_PROCESS.CID = TBL_SFC_WS_TEMPLATE_LINK.CPROCESS_ID
  - TBL_BD_PROCESS.CPROCESS_NO = VW_ERP_MO_DATE_CODE.CPROCESS_NO
  - TBL_BD_PROCESS.CPROCESS_NO = VW_MO_ROUTE.CPROCESS_NO
  - TBL_BD_PROCESS.CPROCESS_NAME = VM_ERP_MATERIAL_RETURN_ITEM.CPROCESS
  - TBL_BD_PROCESS.CPROCESS_NAME = VM_ERP_MATERIAL_RETURN_REQUEST_ITEM.CPROCESS
  - TBL_BD_PROCESS.CID = TBL_EAP_PATTERN_PLAT.CPROCESS_ID
  - TBL_BD_PROCESS.CID = TBL_EAP_THREE_D_RECORD.CPROCESS_ID
  - TBL_BD_PROCESS.CID = TBL_SPC_CONTROL_CHARACTERISTIC.CPROCESS_ID
  - TBL_BD_PROCESS.CID = TBL_MEP_MATERIAL_PARAM.CPROCESS_ID

---

#### 15 外协产品工序表 ( TBL_BD_PROCESS_OUTS )
- **业务含义**：包含了需要外协的生产产品与其外协工序的关联关系
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CPROCESS_CONTROL_TYPE | long? | 是 | - | 工序管控类型 |
| CPROCESS_DESC | string | 是 | - | 工序描述 |
| CPROCESS_ID | long? | 是 | - | 标准工序ID，对应TBL_BD_PROCESS.CID |
| CPROCESS_NAME | string | 是 | - | 工序名称 |
| CPROCESS_NO | string | 是 | - | 工序编码 |
| CPROCESS_SHORT_CODE | string | 是 | - | 工序简称 |
| CPRODUCT_ITEM_NO | string | 是 | - | 外协产品料号，对应TBL_BD_ITEM.CITEM_NO |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_BD_PROCESS_OUTS.CPRODUCT_ITEM_NO = TBL_BD_ITEM.CITEM_NO
  - TBL_BD_PROCESS_OUTS.CPROCESS_ID = TBL_BD_PROCESS.CID

---

#### 16 编码规则定义表 ( TBL_BD_RULE )
- **业务含义**：包含了在MES系统中维护的编码规则列表
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CRULE_NAME | string | 是 | - | 规则名称 |
| CRULE_NO | string | 是 | - | 规则编码 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_BD_RULE.CID = TBL_BD_TEMPLATE.CRULE_ID

---

#### 17 供应商信息表 ( TBL_BD_SUPPLIER )
- **业务含义**：包含了在MES系统中维护的物料供应商、设备供应商信息列表
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CADDRESS | string | 是 | - | 地址 |
| CEMAIL | string | 是 | - | 电子邮箱 |
| CPHONE | string | 是 | - | 联系电话 |
| CREMARK | string | 是 | - | 备注 |
| CSOURCE_ID | string | 是 | - | 来源系统ID |
| CSUPPLIER_DESC | string | 是 | - | 供应商描述 |
| CSUPPLIER_NAME | string | 是 | - | 供应商全称 |
| CSUPPLIER_NO | string | 是 | - | 供应商编码 |
| CSUPPLIER_SHORT | string | 是 | - | 供应商简称 |
| CSUPPLIER_SHORT_NO | string | 是 | - | 供应商简称编码 |
| CUSER | string | 是 | - | 联系人 |
| CID | long | 否 | - | 主键ID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_BD_SUPPLIER.CID = TBL_WMS_ITEM_BARCODE.CSUPPLIER_ID
  - TBL_BD_SUPPLIER.CID = TBL_SRM_PO.CSUPPLIER_ID
  - TBL_BD_SUPPLIER.CID = TBL_SRM_RECEIVING.CSUPPLIER_ID
  - TBL_BD_SUPPLIER.CID = TBL_SHEET_LINK_PP.CSUPPLIER_ID
  - TBL_BD_SUPPLIER.CID = TBL_SHEET_LINK_PP.CLINK_SUPPLIER_ID

---

#### 18 模板信息表 ( TBL_BD_TEMPLATE )
- **业务含义**：包含MES系统中维护的可打印的标签的模板配置信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CRULE_ID | long? | 是 | - | 条码规则ID |
| CTEMPLATE_GROUP_ID | long | 否 | - | 模板分组ID，对应TBL_BD_TEMPLATE_GROUP.CID |
| CTEMPLATE_NAME | string | 是 | - | 模板名称 |
| CTEMPLATE_NO | string | 是 | - | 模板编码 |
| CTEMPLATE_PATH | string | 是 | - | 模板层级路径 |
| CID | long | 否 | - | 主键ID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_BD_TEMPLATE.CTEMPLATE_GROUP_ID = TBL_BD_TEMPLATE_GROUP.CID
  - TBL_BD_TEMPLATE.CRULE_ID = TBL_BD_RULE.CID
  - TBL_BD_TEMPLATE.CID = TBL_SFC_PACKAGE_LABEL_LINK.CTEMPLATE_ID

---

#### 19 模板分组表 ( TBL_BD_TEMPLATE_GROUP )
- **业务含义**：包含MES系统中维护的可打印的标签的模板的组别信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CTEMPLATE_GROUP_NAME | string | 是 | - | 模板分组名称 |
| CTEMPLATE_GROUP_NO | string | 是 | - | 模板分组编码 |
| CID | long | 否 | - | 主键ID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_BD_TEMPLATE_GROUP.CID = TBL_BD_TEMPLATE.CTEMPLATE_GROUP_ID

---

#### 20 工作中心表 ( TBL_BD_WC )
- **业务含义**：包含MES系统中维护的工作中心信息，包括生产设备、环境设备、测试设备等
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CID | long | 否 | - | 主键ID |
| CIS_LINK_CONFIG | string | 是 | - | 是否已配置管控信息（Y已配置，N或空未配置） |
| CIS_LINK_TYPE | string | 是 | - | 是否已配置关联物料类别（Y已配置，N或空未配置） |
| CPARENT | long? | 是 | - | 上级工作中心ID，对应TBL_BD_WC.CID |
| CWC_NAME | string | 是 | - | 工作中心名称 |
| CWC_NO | string | 是 | - | 工作中心编码 |
| CWC_TYPE | long? | 是 | - | 工作中心类型 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_BD_WC.CPARENT = TBL_BD_WC.CID
  - TBL_BD_WC.CID = TBL_BD_WC_ITEMTYPE_LINK.CWC_ID
  - TBL_BD_WC.CID = TBL_BD_WC_PROCESS_LINK.CWC_ID
  - TBL_BD_WC.CID = TBL_QM_ASSAY_LOG.CWC_ID
  - TBL_BD_WC.CID = TBL_QM_MEDICINE_TANK.CWC_ID
  - TBL_BD_WC.CID = TBL_QM_PL_LOG.CWC_ID
  - TBL_BD_WC.CID = TBL_EAM_PM_TEMP_WC_LINK.CWC_ID
  - TBL_BD_WC.CID = TBL_EAM_MAINTAIN_TASK.CWC_ID
  - TBL_BD_WC.CID = TBL_EAM_REPAIR.CWC_ID
  - TBL_BD_WC.CID = TBL_SFC_RECIPE_LOT.CSU_ID
  - TBL_BD_WC.CID = TBL_SFC_RECIPE_PRODUCT.CSU_ID
  - TBL_BD_WC.CID = TBL_SFC_WS_LOG.CWC_ID
  - TBL_BD_WC.CID = TBL_SFC_WS_TEMPLATE_LINK.CWC_ID
  - TBL_BD_WC.CID = TBL_MO.CWC_ID
  - TBL_BD_WC.CID = TBL_OUTSOURCE_SHIFT_EMPLOYEE.CWC_ID
  - TBL_BD_WC.CID = TBL_SPC_CONTROL_CHARACTERISTIC.CWC_ID

---

#### 21 工作中心与物料类别关联 ( TBL_BD_WC_ITEMTYPE_LINK )
- **业务含义**：描述了哪些类型的物料可与哪个工作中心进行关联，关联信息用于后续物料防错逻辑
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CITEM_TYPE_ID | long? | 是 | - | 物料类型ID，对应TBL_BD_ITEM_TYPE.CID |
| CREMARK | string | 是 | - | 备注 |
| CWC_ID | long | 否 | - | 工作中心ID，对应TBL_BD_WC.CID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_BD_WC_ITEMTYPE_LINK.CWC_ID = TBL_BD_WC.CID
  - TBL_BD_WC_ITEMTYPE_LINK.CITEM_TYPE_ID = TBL_BD_ITEM_TYPE.CID

---

#### 22 工作中心与工序关系表 ( TBL_BD_WC_PROCESS_LINK )
- **业务含义**：描述了哪些工序与哪个工作中心进行关联
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CPROCESS_ID | long | 否 | - | 工序ID，对应TBL_BD_PROCESS.CID |
| CSEQ | int? | 是 | - | 工序顺序 |
| CWC_ID | long | 否 | - | 工作中心ID，对应TBL_BD_WC.CID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_BD_WC_PROCESS_LINK.CWC_ID = TBL_BD_WC.CID
  - TBL_BD_WC_PROCESS_LINK.CPROCESS_ID = TBL_BD_PROCESS.CID

---

#### 23 数据集 ( TBL_MD_DATASET )
- **业务含义**：包含MES系统中维护的数据集信息，可用于后续配置表单页面、配置打印数据等
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CDATASET_CONDITION | string | 是 | - | 数据集参数Json字符串 |
| CDATASET_TYPE | DataSetTypeEnum | 否 | - | 数据集类型（0:表,1:视图,2:自定义脚本,3:存储过程） |
| CDATASOURCE_ID | long | 否 | - | 数据源ID |
| CNAME | string | 是 | - | 数据集名称 |
| desc | string | 是 | - | 参数描述 |
| key | string | 是 | - | 参数名称 |
| value | string | 是 | - | 参数值 |
| CID | long | 否 | - | 主键ID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_MD_DATASET.CID = TBL_MSG_EVENT.CDATASET_ID

---

### 2.3 消息推送

> 本章节数据来源于 Excel 工作表：`消息推送`

#### 24 消息事件表 ( TBL_MSG_EVENT )
- **业务含义**：包含了需要推送的特定消息具体事件描述
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CDATASET_ID | long? | 是 | - | 数据集ID，对应TBL_MD_DATASET.CID |
| CDESC | string | 是 | - | 描述 |
| CEXPRESSION | string | 是 | - | 表达式 |
| CFREQUENCY | long? | 是 | - | 频率(0:小时,1:每天,2:每周,3:每月) |
| CINDICAROR | string | 是 | - | 指标 |
| CMSG_GROUP_ID | long? | 是 | - | 消息群组ID，对应TBL_MSG_GROUP.CID |
| CRULE | string | 是 | - | 规则 |
| CSCHEDULE_TASK_ID | int? | 是 | - | 调度任务ID |
| CSEQ | int? | 是 | - | 序号 |
| CTARGET | string | 是 | - | 目标 |
| CTEMPLATE_ID | long? | 是 | - | 消息模板ID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_MSG_EVENT.CDATASET_ID = TBL_MD_DATASET.CID
  - TBL_MSG_EVENT.CMSG_GROUP_ID = TBL_MSG_GROUP.CID
  - TBL_MSG_EVENT.CTEMPLATE_ID = TBL_BD_TEMPLATE.CID

---

#### 25 消息群组 ( TBL_MSG_GROUP )
- **业务含义**：包含了消息推送程序可推送的群组，推送事件以群组为单位
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CGROUP_CODE | string | 是 | - | 群组编码 |
| CGROUP_DESC | string | 是 | - | 群组描述 |
| CGROUP_NAME | string | 是 | - | 群组名称 |
| CTHIRD_PARTY_PARAM | string | 是 | - | 第三方参数 |
| CID | long | 否 | - | 主键 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_MSG_GROUP.CID = TBL_MSG_EVENT.CMSG_GROUP_ID
  - TBL_MSG_GROUP.CID = TBL_MSG_GROUP_USER.CGROUP_ID

---

#### 26 消息群组和用户 ( TBL_MSG_GROUP_USER )
- **业务含义**：包含了推送群组与MES系统用户之间的关联关系
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CGROUP_ID | long | 否 | - | 群组ID，对应TBL_MSG_GROUP.CID |
| CUSER_ID | long | 否 | - | 用户ID，对应TBL_SYS_USER.CID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_MSG_GROUP_USER.CGROUP_ID = TBL_MSG_GROUP.CID
  - TBL_MSG_GROUP_USER.CUSER_ID = TBL_SYS_USER.CID

---

#### 27 预警频率配置表 ( TBL_MSG_PUSH_FREQUENCY )
- **业务含义**：描述消息推送事件的推送频率的配置信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CDESC | string | 是 | - | 描述 |
| CSCHEDULE | string | 是 | - | 频率(Cron表达式) |
| CSEQ | int? | 是 | - | 序号 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：无

---

#### 28 消息发送日志表 ( TBL_MSG_SEND_LOG )
- **业务含义**：包含了消息推送事件发送的日志记录信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CACCEPT_DATETIME | DateTime? | 是 | - | 接收日期 |
| CCLOSE_DATETIME | DateTime? | 是 | - | 关闭日期 |
| CCONFIRM_DATETIME | DateTime? | 是 | - | 确认日期 |
| CDELETE_DATETIME | DateTime? | 是 | - | 删除日期 |
| CMSG_CONTENT | string | 是 | - | 消息内容 |
| CREMARK | string | 是 | - | 备注 |
| CSEND_DATETIME | DateTime? | 是 | - | 发送日期 |
| CSEND_TYPE | string | 是 | - | 发送类型 |
| CSTATUS | int? | 是 | - | 状态 |
| CUSER_ID | string | 是 | - | 处理人，对应TBL_SYS_USER.CID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_MSG_SEND_LOG.CUSER_ID = TBL_SYS_USER.CID

---

#### 29 消息推送用户 ( TBL_MSG_USER )
- **业务含义**：包含了MES系统用户与企业微信账号的对应关系
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CACCOUNT | string | 是 | - | 企业微信或钉钉账号 |
| CUSER_ID | long? | 是 | - | 用户表ID，对应TBL_SYS_USER.CID |
| CUSER_NAME | string | 是 | - | 姓名 |
| CUSER_TYPE | string | 是 | - | 类型 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_MSG_USER.CUSER_ID = TBL_SYS_USER.CID

---

### 2.4 设备联机

> 本章节数据来源于 Excel 工作表：`设备联机`

#### 30 设备报警记录 ( TBL_EAP_ALARM )
- **业务含义**：包含了在边缘网关中联机的设备的所有的报警信息
- **所属数据库**：192.168.49.10.CIEAP、192.168.49.18.CIEAP
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CALARM_LEVEL | int? | 是 | - | 报警等级 |
| CDATETIME_CREATED | DateTime | 否 | - | 创建时间 |
| CDATETIME_MODIFIED | DateTime? | 是 | - | 修改时间 |
| CDEVICE_ID | int | 否 | - | 设备ID， 对应TBL_EAP_DEVICE.CDEVICE_ID |
| CEND_TIME | DateTime? | 是 | - | 报警结束时间 |
| CERROR_ID | int? | 是 | - | 报警类型ID |
| CERROR_MESSAGE | string | 是 | - | 报警信息 |
| CERROR_NO | string | 是 | - | 报警编码 |
| CITEM_NO | string | 是 | - | 料号，对应TBL_BD_ITEM.CITEM_NO |
| CLOT_NO | string | 是 | - | 批次号 |
| CORDER_NO | string | 是 | - | 工单号，对应TBL_MO.CMO_LOT |
| CSTART_TIME | DateTime? | 是 | - | 报警开始时间 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAP_ALARM.CDEVICE_ID = TBL_EAP_DEVICE.CDEVICE_ID
  - TBL_EAP_ALARM.CITEM_NO = TBL_BD_ITEM.CITEM_NO
  - TBL_EAP_ALARM.CORDER_NO = TBL_MO.CMO_LOT

---

#### 31 AOI或者VRS数据主表 ( TBL_EAP_AOI_DETECTIONS )
- **业务含义**：包含了AOI设备和VRS设备的检测数据主体信息，其中包括多个品牌的机器，如锋明、宜美智等
- **所属数据库**：192.168.49.18.CIEAP
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CBARCODE | string | 是 | - | 板码 |
| CBRAND | string | 是 | - | 品牌 |
| CDATETIME_CREATED | DateTime | 否 | - | 创建时间 |
| CDATETIME_MODIFIED | DateTime? | 是 | - | 修改时间 |
| CDEVICE_ID | int | 否 | - | 设备ID， 对应TBL_EAP_DEVICE.CDEVICE_ID |
| CITEM_NO | string | 是 | - | 上传料号 |
| CLAYER | string | 是 | - | 层别 |
| CLOT_NO | string | 是 | - | 批次号 |
| CMAP_ITEM_NO | string | 是 | - | 映射料号，对应TBL_BD_ITEM.CITEM_NO |
| CPRINT_CODE | string | 是 | - | 印码 |
| CRESULT | string | 是 | - | 检测结果，合格；不合格 |
| CTEST_END_TIME | DateTime? | 是 | - | 测试结束时间 |
| CTEST_START_TIME | DateTime? | 是 | - | 测试开始时间 |
| CTEST_TIME | string | 是 | - | 检测时间 |
| CTOTAL_QTY | int? | 是 | - | 总数量 |
| CID | long | 否 | - | 主键ID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAP_AOI_DETECTIONS.CDEVICE_ID = TBL_EAP_DEVICE.CDEVICE_ID
  - TBL_EAP_AOI_DETECTIONS.CMAP_ITEM_NO = TBL_BD_ITEM.CITEM_NO
  - TBL_EAP_AOI_DETECTIONS.CID = TBL_EAP_AOI_DETECTIONS_DTL.CDETECTION_ID

---

#### 32 AOI或VRS数据明细表 ( TBL_EAP_AOI_DETECTIONS_DTL )
- **业务含义**：包含了AOI设备和VRS设备的检测数据明细信息
- **所属数据库**：192.168.49.18.CIEAP
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CDATETIME_CREATED | DateTime | 否 | - | 创建时间 |
| CDATETIME_MODIFIED | DateTime? | 是 | - | 修改时间 |
| CDEFECT_NO | string | 是 | - | 缺陷编号 |
| CDETECTION_ID | long | 否 | - | 主表ID，对应TBL_EAP_AOI_DETECTIONS.CID |
| CIMG_PATH | string | 是 | - | 图片路径 |
| CIS_FLAG | int? | 是 | - | 标记位 |
| CNG_CONTENT | string | 是 | - | NG内容 |
| CNG_NO | string | 是 | - | NG编号 |
| COORDINATE_X | string | 是 | - | X坐标 |
| COORDINATE_Y | string | 是 | - | Y坐标 |
| CPOSITION | string | 是 | - | 位置 |
| CSERVER_IMG_PATH | string? | 是 | - | 服务器上图片路径 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAP_AOI_DETECTIONS_DTL.CDETECTION_ID = TBL_EAP_AOI_DETECTIONS.CID

---

#### 33 联机API调用记录 ( TBL_EAP_API_RECORDS )
- **业务含义**：包含所有通过WebAPI进行联机的设备的接口调用日志
- **所属数据库**：192.168.49.10.CIEAP、192.168.49.18.CIEAP
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CDATA_TYPE | string | 是 | - | 数据类型（如 GET/POST） |
| CDATETIME_CREATED | DateTime | 否 | - | 创建时间 |
| CDEVICE_NAME | string | 是 | - | 设备名称 |
| CINTERFACE | string | 是 | - | 接口地址 |
| CINTERFACE_NAME | string | 是 | - | 接口名称 |
| CREMARK | string | 是 | - | 备注 |
| CREQUEST | string | 是 | - | 请求报文 |
| CRESPONSE | string | 是 | - | 响应报文 |
| CSERVER_ID | string | 是 | - | 服务器标识 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：无

---

#### 34 放板机状态监控表，两分钟更新一次 ( TBL_EAP_AUTO_PULL_MACHINE )
- **业务含义**：描述每台放板机的实时状态，状态信息每两分钟更新一次
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CDATETIME_MODIFIED | DateTime | 否 | - | 修改时间 |
| CIS_BOARD | string | 是 | - | 是否有板，Y：是；N：否 |
| CIS_MES_MODEL | string | 是 | - | 是否MES模式，Y：是；N：否 |
| CIS_ONLINE | string | 是 | - | 是否在线，Y：是；N：否 |
| CIS_RUN | string | 是 | - | 是否运行，Y：是；N：否 |
| CPULL_MACHINE_NAME | string | 是 | - | 放板机名称 |
| CPULL_MACHINE_NO | string | 是 | - | 放板机编号（后面加"-放板机"为配置的DEVICE_NAME） |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：无

---

#### 35 班通参数主表 ( TBL_EAP_BT_PARAM )
- **业务含义**：描述了班通线宽测量仪的下发配方参数主表信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CITEM_NO | string | 是 | - | 料号，对应TBL_BD_ITEM.CITEM_NO |
| CLAYER_NAME | string | 是 | - | 层别名称 |
| CPART_NUM | string | 是 | - | 制造部件 |
| CPROCESS | string | 是 | - | 工序，对应TBL_BD_PROCESS.CPROCESS_NO |
| CID | long | 否 | - | 主键ID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAP_BT_PARAM.CITEM_NO = TBL_BD_ITEM.CITEM_NO
  - TBL_EAP_BT_PARAM.CPROCESS = TBL_BD_PROCESS.CPROCESS_NO
  - TBL_EAP_BT_PARAM.CID = TBL_EAP_BT_PARAM_DTL.CMAIN_ID

---

#### 36 班通参数明细表 ( TBL_EAP_BT_PARAM_DTL )
- **业务含义**：描述了班通线宽测量仪的下发配方参数具体项目信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CDATA_TYPE | string | 是 | - | 数据类型 |
| CMAIN_ID | long | 否 | - | 主表ID，对应TBL_EAP_BT_PARAM.CID |
| CMAX_VALUE | decimal? | 是 | - | 最大值 |
| CMEASURE_ITEM_NAME | string | 是 | - | 测量项目名称 |
| CMEASURE_TYPE | string | 是 | - | 测量类型 |
| CMIN_VALUE | decimal? | 是 | - | 最小值 |
| CSTAND_VALUE | decimal? | 是 | - | 标准值 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAP_BT_PARAM_DTL.CMAIN_ID = TBL_EAP_BT_PARAM.CID

---

#### 37 联机测点TAG实时状态表 ( TBL_EAP_CURRENT_DATA )
- **业务含义**：包含了在边缘网关中联机的设备的所配置的测点的实时采集数值
- **所属数据库**：192.168.49.10.CIEAP、192.168.49.18.CIEAP
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CDATETIME_MODIFIED | DateTime? | 是 | - | 修改时间 |
| CDEVICE_ID | int | 否 | - | 设备ID， 对应TBL_EAP_DEVICE.CDEVICE_ID |
| CDEVICE_NAME | string | 是 | - | 设备名称 |
| CDEVICE_SERIAL | int | 否 | - | 设备序号 |
| CDT | DateTime? | 是 | - | 数据时间 |
| CSERVER_SERIAL | int | 否 | - | 服务器序号 |
| CTAG_ID | int | 否 | - | 测点ID（关联测点配置）, 对应TBL_EAP_TAG.CTAG_ID |
| CTAG_NAME | string | 是 | - | 测点名称 |
| CTYPE | string | 是 | - | 数据类型 |
| CVALUE | float? | 是 | - | 数值 |
| CVALUE_STRING | string | 是 | - | 字符串值 |
| CVALUE_TYPE | int | 否 | - | 值类型 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAP_CURRENT_DATA.CDEVICE_ID = TBL_EAP_DEVICE.CDEVICE_ID
  - TBL_EAP_CURRENT_DATA.CTAG_ID = TBL_EAP_TAG.CTAG_ID

---

#### 38 联机数据测点采集信息表(分表) ( TBL_EAP_DATA_YYYYMM )
- **业务含义**：包含了在边缘网关中联机的设备的所配置的测点的历史采集数值，分表格式为TBL_EAP_DATA_202605
- **所属数据库**：192.168.49.10.CIEAP、192.168.49.18.CIEAP
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CDATETIME_CREATED | DateTime? | 是 | - | 创建时间 |
| CDEVICE_ID | int? | 是 | - | 设备ID， 对应TBL_EAP_DEVICE.CDEVICE_ID |
| CDT | DateTime? | 是 | - | 数据时间 |
| CSERVER_ID | int? | 是 | - | 服务器序号 |
| CTAG_ID | int? | 是 | - | 测点ID（关联测点配置）, 对应TBL_EAP_TAG.CTAG_ID |
| CTYPE | string | 是 | - | 数据类型 |
| CVALUE | float? | 是 | - | 测点数值 |
| CVALUE_STRING | string | 是 | - | 测点数值(字符串) |
| CVALUE_TYPE | byte? | 是 | - | 值类型 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAP_DATA_YYYYMM.CDEVICE_ID = TBL_EAP_DEVICE.CDEVICE_ID
  - TBL_EAP_DATA_YYYYMM.CTAG_ID = TBL_EAP_TAG.CTAG_ID

---

#### 39 联机设备列表 ( TBL_EAP_DEVICE )
- **业务含义**：包含了在边缘网关中联机的设备主体信息
- **所属数据库**：192.168.49.10.CIEAP、192.168.49.18.CIEAP
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CADDRESS | string | 是 | - | 设备地址 |
| CDATETIME_CREATED | DateTime | 否 | - | 创建时间 |
| CDATETIME_MODIFIED | DateTime | 否 | - | 修改时间 |
| CDEVICE_ID | int | 否 | - | 设备编号 |
| CDEVICE_NAME | string | 是 | - | 设备名称 |
| CDEVICE_SERIAL | int | 否 | - | 设备序号 |
| CID | long | 否 | - | 主键ID |
| CIP | string | 是 | - | 设备IP |
| CLOT | string | 是 | - | 当前批次号 |
| COEE | decimal? | 是 | - | OEE指标 |
| CPORT | int? | 是 | - | 设备端口 |
| CPRODUCT | string | 是 | - | 当前产品信息 |
| CREMARK | string | 是 | - | 备注 |
| CSERVER_SERIAL | int | 否 | - | 服务器序号 |
| CSTATUS | int | 否 | - | 设备状态码 |
| CSTATUS_TIME | DateTime | 否 | - | 状态更新时间 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAP_DEVICE.CDEVICE_ID = TBL_EAP_ALARM.CDEVICE_ID
  - TBL_EAP_DEVICE.CDEVICE_ID = TBL_EAP_AOI_DETECTIONS.CDEVICE_ID
  - TBL_EAP_DEVICE.CDEVICE_ID = TBL_EAP_CURRENT_DATA.CDEVICE_ID
  - TBL_EAP_DEVICE.CDEVICE_ID = TBL_EAP_DATA_YYYYMM.CDEVICE_ID
  - TBL_EAP_DEVICE.CDEVICE_ID = TBL_EAP_HONGSHENG_RECORDS.CDEVICE_ID
  - TBL_EAP_DEVICE.CDEVICE_ID = TBL_EAP_HONGSHENG_TM_RECORDS.CDEVICE_ID
  - TBL_EAP_DEVICE.CDEVICE_ID = TBL_EAP_LWT_DETECTIONS.CDEVICE_ID
  - TBL_EAP_DEVICE.CDEVICE_ID = TBL_EAP_PERIOD.CDEVICE_ID
  - TBL_EAP_DEVICE.CDEVICE_ID = TBL_EAP_PMS_CONTENT.CDEVICE_ID
  - TBL_EAP_DEVICE.CDEVICE_ID = TBL_EAP_PMS_PROD.CDEVICE_ID
  - TBL_EAP_DEVICE.CDEVICE_ID = TBL_EAP_STATUS.CDEVICE_ID
  - TBL_EAP_DEVICE.CDEVICE_ID = TBL_EAP_TAG.CDEVICE_ID
  - TBL_EAP_DEVICE.CDEVICE_ID = TBL_EAP_YUHUI_TEST_RECORDS.CDEVICE_ID
  - TBL_EAP_DEVICE.CDEVICE_ID = TBL_PM_TEMPLATE_LINK_DEVICE.CDEVICE_ID
  - TBL_EAP_DEVICE.CDEVICE_ID = TBL_EAP_ALARM_CONTROL_LINK.CDEVICE_ID
  - TBL_EAP_DEVICE.CDEVICE_ID = TBL_EAP_ITEM_CONTROL_LINK.CDEVICE_ID
  - TBL_EAP_DEVICE.CDEVICE_ID = TBL_EAP_POTION_ITEM_CONTROL_LINK.CDEVICE_ID
  - TBL_EAP_DEVICE.CDEVICE_ID = TBL_EAP_PRODUCE_CONTROL_DEVICE.CDEVICE_ID

---

#### 40 今明图电参数 ( TBL_EAP_GE_PARAM )
- **业务含义**：包含今明图电生产参数下发配方的配置信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CAREA_C | decimal | 否 | - | C面积 |
| CAREA_S | decimal | 否 | - | S面积 |
| CCU_DEN | decimal | 否 | - | 铜密度 |
| CCU_TIME | int | 否 | - | 铜时间 |
| CFB | string | 是 | - | A/B挂 |
| CITEM_NO | string | 是 | - | 料号，对应TBL_BD_ITEM.CITEM_NO |
| CPARAM_STATUS | string | 是 | - | 参数状态  => 试板参数: TESTPLATE   生产参数: PRODUCTION |
| CPART_NUM | string | 是 | - | 制造部件 |
| CREMARK | string | 是 | - | 备注 |
| CSN_DEN | decimal | 否 | - | 锡密度 |
| CSN_TIME | int | 否 | - | 锡时间 |
| CSTATUS | int | 否 | - | 状态，1：可用；0：不可用 |
| CUSE_COUNT | int? | 是 | - | 使用次数 |
| CID | long | 否 | - | 主键ID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAP_GE_PARAM.CITEM_NO = TBL_BD_ITEM.CITEM_NO
  - TBL_EAP_GE_PARAM.CID = TBL_EAP_GE_PARAM_CHANGE_LOG.CPARAMS_ID
  - TBL_EAP_GE_PARAM.CID = TBL_EAP_GE_PARAM_USE_LOG.CPARAMS_ID

---

#### 41 图电参数变更记录表 ( TBL_EAP_GE_PARAM_CHANGE_LOG )
- **业务含义**：包含今明图电生产参数下发配方信息的变更记录
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CAAREA_C | decimal | 否 | - | 变更后C面积 |
| CAAREA_S | decimal | 否 | - | 变更后S面积 |
| CACU_DEN | decimal | 否 | - | 变更后铜密度 |
| CACU_TIME | int | 否 | - | 变更后铜时间 |
| CASN_DEN | decimal | 否 | - | 变更后锡密度 |
| CASN_TIME | int | 否 | - | 变更后锡时间 |
| CBAREA_C | decimal? | 是 | - | 变更前C面积 |
| CBAREA_S | decimal? | 是 | - | 变更前S面积 |
| CBCU_DEN | decimal? | 是 | - | 变更前铜密度 |
| CBCU_TIME | int? | 是 | - | 变更前铜时间 |
| CBSN_DEN | decimal? | 是 | - | 变更前锡密度 |
| CBSN_TIME | int? | 是 | - | 变更前锡时间 |
| CPARAMS_ID | long | 否 | - | 参数主表ID，对应TBL_EAP_GE_PARAM.CID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAP_GE_PARAM_CHANGE_LOG.CPARAMS_ID = TBL_EAP_GE_PARAM.CID

---

#### 42 图电参数下发记录 ( TBL_EAP_GE_PARAM_USE_LOG )
- **业务含义**：包含今明图电生产参数下发配方的下发记录
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CMACHINE_NAME | string | 是 | - | 机台名称 |
| CPARAMS_ID | long | 否 | - | 参数主表ID，对应TBL_EAP_GE_PARAM.CID |
| CWO | string | 是 | - | 工单号，对应TBL_MO.CMO_LOT |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAP_GE_PARAM_USE_LOG.CPARAMS_ID = TBL_EAP_GE_PARAM.CID
  - TBL_EAP_GE_PARAM_USE_LOG.CWO = TBL_MO.CMO_LOT

---

#### 43 金镍测试仪上传数据主表，沉金 ( TBL_EAP_GOLD_NICKEL_TESTER_RECORD )
- **业务含义**：包含金镍测试仪上传的沉金部分的测试主体数据
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CAU_AVG | decimal? | 是 | - | 金含量平均值 |
| CAU_CV | decimal | 否 | - | 金含量变异系数 |
| CAU_DEVIATION | decimal? | 是 | - | 金含量偏差 |
| CAU_MAX_VALUE | decimal? | 是 | - | 金含量最大值 |
| CAU_MIN_VALUE | decimal? | 是 | - | 金含量最小值 |
| CAU_RANGE | decimal? | 是 | - | 金含量范围 |
| CFILE_NAME | string | 是 | - | 文件名 |
| CIMG_1 | string? | 是 | - | 图片1 |
| CIMG_2 | string? | 是 | - | 图片2 |
| CITEM | string | 是 | - | 项目 |
| CMACHINE_TIME | DateTime? | 是 | - | 机器时间 |
| CNI_AVG | decimal? | 是 | - | 镍含量平均值 |
| CNI_CV | decimal? | 是 | - | 镍含量变异系数 |
| CNI_DEVIATION | decimal? | 是 | - | 镍含量偏差 |
| CNI_MAX_VALUE | decimal? | 是 | - | 镍含量最大值 |
| CNI_MIN_VALUE | decimal? | 是 | - | 镍含量最小值 |
| CNI_RANGE | decimal? | 是 | - | 镍含量范围 |
| COPERATOR | string | 是 | - | 操作员，对应TBL_SYS_USER.CUSER_NAME |
| CPROCESS_NAME | string | 是 | - | 过程名称 |
| CPROGRAM_NAME | string | 是 | - | 程序名称 |
| CSAMPLE_NAME | string | 是 | - | 样品名称 |
| CSAMPLE_NO | string | 是 | - | 样品编号 |
| CID | long | 否 | - | 主键ID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAP_GOLD_NICKEL_TESTER_RECORD.CID = TBL_EAP_GOLD_NICKEL_TESTER_RECORD_DETAIL.CRECORD_ID
  - TBL_EAP_GOLD_NICKEL_TESTER_RECORD.COPERATOR = TBL_SYS_USER.CUSER_NAME

---

#### 44 金镍测试仪上传数据明细表，沉金 ( TBL_EAP_GOLD_NICKEL_TESTER_RECORD_DETAIL )
- **业务含义**：包含金镍测试仪上传的沉金部分的测试项目明细数据
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CAU_VALUE | decimal? | 是 | - | 金测量值 |
| CNI_VALUE | decimal? | 是 | - | 镍测量值 |
| CRECORD_ID | long | 否 | - | 主表ID，对应TBL_EAP_GOLD_NICKEL_TESTER_RECORD.CID |
| CSEQ | int? | 是 | - | 序号 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAP_GOLD_NICKEL_TESTER_RECORD_DETAIL.CRECORD_ID = TBL_EAP_GOLD_NICKEL_TESTER_RECORD.CID

---

#### 45 金镍测试仪主表，沉锡 ( TBL_EAP_GOLD_NICKEL_TESTER_RECORD_SN )
- **业务含义**：包含金镍测试仪上传的沉锡部分的测试主体数据
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CFILE_NAME | string | 是 | - | 文件名 |
| CIMG_1 | string? | 是 | - | 图片1 |
| CIMG_2 | string? | 是 | - | 图片2 |
| CITEM | string | 是 | - | 项目 |
| CMACHINE_TIME | DateTime? | 是 | - | 机器时间 |
| COPERATOR | string | 是 | - | 操作员，对应TBL_SYS_USER.CUSER_NAME |
| CPROCESS_NAME | string | 是 | - | 过程名称 |
| CPROGRAM_NAME | string | 是 | - | 程序名称 |
| CSAMPLE_NAME | string | 是 | - | 样品名称 |
| CSAMPLE_NO | string | 是 | - | 样品编号 |
| CSN_AVG | decimal? | 是 | - | 锡含量平均值 |
| CSN_CV | decimal | 否 | - | 锡含量变异系数 |
| CSN_DEVIATION | decimal? | 是 | - | 锡含量偏差 |
| CSN_MAX_VALUE | decimal? | 是 | - | 锡含量最大值 |
| CSN_MIN_VALUE | decimal? | 是 | - | 锡含量最小值 |
| CSN_RANGE | decimal? | 是 | - | 锡含量范围 |
| CID | long | 否 | - | 主键ID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAP_GOLD_NICKEL_TESTER_RECORD_SN.CID = TBL_EAP_GOLD_NICKEL_TESTER_RECORD_SN_DETAIL.CRECORD_ID
  - TBL_EAP_GOLD_NICKEL_TESTER_RECORD_SN.COPERATOR = TBL_SYS_USER.CUSER_NAME

---

#### 46 金镍测试仪明细表，沉锡 ( TBL_EAP_GOLD_NICKEL_TESTER_RECORD_SN_DETAIL )
- **业务含义**：包含金镍测试仪上传的沉锡部分的测试项目明细数据
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CRECORD_ID | long | 否 | - | 主表ID，对应TBL_EAP_GOLD_NICKEL_TESTER_RECORD_SN.CID |
| CSEQ | int? | 是 | - | 序号 |
| CSN_VALUE | decimal? | 是 | - | 锡测量值 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAP_GOLD_NICKEL_TESTER_RECORD_SN_DETAIL.CRECORD_ID = TBL_EAP_GOLD_NICKEL_TESTER_RECORD_SN.CID

---

#### 47 浩硕打靶机参数 ( TBL_EAP_HAOS_PARAM )
- **业务含义**：包含浩硕打靶机生产参数下发配方的配置信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CDATETIME_CREATED | DateTime? | 是 | - | 创建时间（datetime类型，允许为空） |
| CDATETIME_MODIFIED | DateTime? | 是 | - | 修改时间（datetime类型，允许为空） |
| CDistA1A2 | decimal? | 是 | - | AIA2靶距（decimal类型，精度18位，小数位6位，允许为空） |
| CDistA1B1 | decimal? | 是 | - | AIB1靶距（decimal类型，精度18位，小数位6位，允许为空） |
| CDistA1C1_X | decimal? | 是 | - | A1C1 X距离（decimal类型，精度18位，小数位6位，允许为空） |
| CDistA1C1_Y | decimal? | 是 | - | A1C1 Y距离（decimal类型，精度18位，小数位6位，允许为空） |
| CDistC1C2 | decimal? | 是 | - | CIC2靶距（decimal类型，精度18位，小数位6位，允许为空） |
| CDistC1D1 | decimal? | 是 | - | CID1靶距（decimal类型，精度18位，小数位6位，允许为空） |
| CDrillstyle | string | 是 | - | 钻靶型式（varchar类型，长度50，允许为空） |
| CENTERPRISE_CODE | long? | 是 | - | 企业编码（bigint类型，允许为空） |
| CFrontToA1A2 | decimal? | 是 | - | AIA2至板前缘（decimal类型，精度18位，小数位6位，允许为空） |
| CINSTANCE_ID | string | 是 | - | 实例ID（varchar类型，长度256，允许为空） |
| CJobname | string | 是 | - | 料号（varchar类型，长度50，允许为空） |
| CLength | decimal? | 是 | - | 板长（decimal类型，精度18位，小数位6位，允许为空） |
| CLot_NO | string | 是 | - | 批次号，对应TBL_MO.CMO_LOT |
| CORG_CODE | long? | 是 | - | 组织编码（bigint类型，允许为空） |
| Count | int? | 是 | - | 数量（int类型，允许为空） |
| CRecipetime | string | 是 | - | 配方生成时间戳（varchar类型，长度50，允许为空） |
| CROWREMARK | string | 是 | - | 行备注（varchar(max)类型，允许为空，可存储长文本） |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
| CThickness | decimal? | 是 | - | 板厚（decimal类型，精度18位，小数位6位，允许为空） |
| CWidth | decimal? | 是 | - | 板宽（decimal类型，精度18位，小数位6位，允许为空） |
- **关联关系**：无

---

#### 48 放板机心跳记录 ( TBL_EAP_HEARTBEAT )
- **业务含义**：包含每台放板机上传的心跳记录
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CDEVICE_NAME | string | 是 | - | 设备名称 |
| CLOGIN_USER | string | 是 | - | 登录用户，对应TBL_SYS_USER.CUSER_NAME |
| CREMARK | string | 是 | - | 备注 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAP_HEARTBEAT.CLOGIN_USER = TBL_SYS_USER.CUSER_NAME

---

#### 49 宏胜裁磨机结批数据 ( TBL_EAP_HONGSHENG_RECORDS )
- **业务含义**：宏胜裁磨机上传的生产数据主表
- **所属数据库**：192.168.49.18.CIEAP
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CDATETIME_CREATED | DateTime | 否 | - | 创建时间 |
| CDATETIME_MODIFIED | DateTime? | 是 | - | 修改时间 |
| CDEVICE_ID | int | 否 | - | 设备ID， 对应TBL_EAP_DEVICE.CDEVICE_ID |
| CITEM_NO | string | 是 | - | 料号，对应TBL_BD_ITEM.CITEM_NO |
| CLOT_IN_QTY | int? | 是 | - | 投入数量 |
| CLOT_NO | string | 是 | - | 批次号 |
| CLOT_OUT_QTY | int? | 是 | - | 产出数量 |
| CLOT_QTY | int? | 是 | - | 批次数量 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAP_HONGSHENG_RECORDS.CDEVICE_ID = TBL_EAP_DEVICE.CDEVICE_ID
  - TBL_EAP_HONGSHENG_RECORDS.CITEM_NO = TBL_BD_ITEM.CITEM_NO

---

#### 50 宏胜测厚机测试数据 ( TBL_EAP_HONGSHENG_TM_RECORDS )
- **业务含义**：宏胜裁磨机上传的测试数据
- **所属数据库**：192.168.49.18.CIEAP
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| Average | string | 是 | - | 平均值 |
| CCOUNT | string | 是 | - | 计数值 |
| CDATETIME_CREATED | DateTime? | 是 | - | 创建时间 |
| CDATETIME_MODIFIED | DateTime? | 是 | - | 修改时间 |
| CDEVICE_ID | int? | 是 | - | 设备ID， 对应TBL_EAP_DEVICE.CDEVICE_ID |
| Container | string | 是 | - | 容器号 |
| CopperLowerLimit | string | 是 | - | 铜厚下限 |
| CopperThickness | string | 是 | - | 铜厚测量值 |
| CopperUpperLimit | string | 是 | - | 铜厚上限 |
| CPERCENT | string | 是 | - | 百分比 |
| CTIME | string | 是 | - | 测量时间 |
| DeviceCode | string | 是 | - | 设备编码 |
| DeviceName | string | 是 | - | 设备名称 |
| DeviceStatus | string | 是 | - | 设备状态 |
| DivFact | string | 是 | - | 分度系数 |
| DownCuResult | string | 是 | - | 下铜判定结果 |
| JudgmentResults | string | 是 | - | 判定结果 |
| LeftPointA | string | 是 | - | 左侧A点测量值 |
| LeftPointB | string | 是 | - | 左侧B点测量值 |
| LeftPointC | string | 是 | - | 左侧C点测量值 |
| LeftPointD | string | 是 | - | 左侧D点测量值 |
| LowerCopper | string | 是 | - | 下铜厚测量值 |
| LowerCopperlowerlimit | string | 是 | - | 下铜厚下限 |
| LowerCopperupperlimit | string | 是 | - | 下铜厚上限 |
| LowerLimit | string | 是 | - | 板厚下限 |
| MACHINE_IP | string | 是 | - | 设备IP |
| MeanValue | string | 是 | - | 均值 |
| MethodName | string | 是 | - | 上报方法名 |
| MiddlePointA | string | 是 | - | 中间A点测量值 |
| MiddlePointB | string | 是 | - | 中间B点测量值 |
| MiddlePointC | string | 是 | - | 中间C点测量值 |
| MiddlePointD | string | 是 | - | 中间D点测量值 |
| PartNo | string | 是 | - | 料号，对应TBL_BD_ITEM.CITEM_NO |
| RightPointA | string | 是 | - | 右侧A点测量值 |
| RightPointB | string | 是 | - | 右侧B点测量值 |
| RightPointC | string | 是 | - | 右侧C点测量值 |
| RightPointD | string | 是 | - | 右侧D点测量值 |
| Thickness | string | 是 | - | 板厚测量值 |
| UpCuResult | string | 是 | - | 上铜判定结果 |
| UpperLimit | string | 是 | - | 板厚上限 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAP_HONGSHENG_TM_RECORDS.CDEVICE_ID = TBL_EAP_DEVICE.CDEVICE_ID

---

#### 51 活全压机数据，每两分钟从Mysql采集 ( TBL_EAP_HQ_PRESS_PRODUCTION )
- **业务含义**：活全压机的生产数据，由定时器从其它数据库定时采集更新
- **所属数据库**：192.168.49.10.CIEAP
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CDATETIME_CREATED | DateTime? | 是 | - | 创建时间 |
| CDATETIME_MODIFIED | DateTime? | 是 | - | 修改时间 |
| CDEVICE_NO | string? | 是 | - | 设备编号 |
| Job_No | string | 是 | - | 作业号 |
| Lot_No | string | 是 | - | 批次号 |
| Mat_Pcs | string | 是 | - | 板数 |
| Mat_Press_PV | string | 是 | - | 材料压力实测值 |
| Mat_Press_SV | string | 是 | - | 材料压力设定值 |
| Mat_Size_L | string | 是 | - | 物料长度 |
| Mat_Size_W | string | 是 | - | 物料宽度 |
| Now_Vacuum | string | 是 | - | 当前真空度 |
| Part_No | string | 是 | - | 料号，对应TBL_BD_ITEM.CITEM_NO |
| PRESS_TPDIS_LYR01 | string | 是 | - | 层厚度偏差01 |
| PRESS_TPDIS_LYR02 | string | 是 | - | 层厚度偏差02 |
| PRESS_TPDIS_LYR03 | string | 是 | - | 层厚度偏差03 |
| PRESS_TPDIS_LYR04 | string | 是 | - | 层厚度偏差04 |
| PRESS_TPDIS_LYR05 | string | 是 | - | 层厚度偏差05 |
| PRESS_TPDIS_LYR06 | string | 是 | - | 层厚度偏差06 |
| PRESS_TPDIS_LYR07 | string | 是 | - | 层厚度偏差07 |
| PRESS_TPDIS_LYR08 | string | 是 | - | 层厚度偏差08 |
| PRESS_TPDIS_LYR09 | string | 是 | - | 层厚度偏差09 |
| PRESS_TPDIS_LYR10 | string | 是 | - | 层厚度偏差10 |
| PRESS_TPDIS_LYR11 | string | 是 | - | 层厚度偏差11 |
| PRESS_TPDIS_LYR12 | string | 是 | - | 层厚度偏差12 |
| PRESS_TPDIS_LYR13 | string | 是 | - | 层厚度偏差13 |
| PRESS_TPDIS_LYR14 | string | 是 | - | 层厚度偏差14 |
| PRESS_TPDIS_LYR15 | string | 是 | - | 层厚度偏差15 |
| PRESS_TPDIS_LYR16 | string | 是 | - | 层厚度偏差16 |
| PRESS_TPDIS_LYR17 | string | 是 | - | 层厚度偏差17 |
| PRESS_TPDIS_LYR18 | string | 是 | - | 层厚度偏差18 |
| PRESS_TPDIS_LYR19 | string | 是 | - | 层厚度偏差19 |
| PRESS_TPDIS_LYR20 | string | 是 | - | 层厚度偏差20 |
| PRESS_TPDIS_MAT01 | string | 是 | - | 材料厚度偏差01 |
| PRESS_TPDIS_MAT02 | string | 是 | - | 材料厚度偏差02 |
| PRESS_TPDIS_MAT03 | string | 是 | - | 材料厚度偏差03 |
| PRESS_TPDIS_MAT04 | string | 是 | - | 材料厚度偏差04 |
| PRESS_TPDIS_MAT05 | string | 是 | - | 材料厚度偏差05 |
| PRESS_TPDIS_MAT06 | string | 是 | - | 材料厚度偏差06 |
| PRESS_TPDIS_MAT07 | string | 是 | - | 材料厚度偏差07 |
| PRESS_TPDIS_MAT08 | string | 是 | - | 材料厚度偏差08 |
| PRESS_TPDIS_MAT09 | string | 是 | - | 材料厚度偏差09 |
| PRESS_TPDIS_MAT10 | string | 是 | - | 材料厚度偏差10 |
| PRESS_TPDIS_MAT11 | string | 是 | - | 材料厚度偏差11 |
| PRESS_TPDIS_MAT12 | string | 是 | - | 材料厚度偏差12 |
| Recipe_Name | string | 是 | - | 配方名称 |
| System_Press | string | 是 | - | 系统压力 |
| TEMP_AVG | string | 是 | - | 平均温度 |
| TEMP_SV | string | 是 | - | 温度设定值 |
| Time_Stamp | DateTime | 否 | - | 时间戳 |
| Time_Stamp_ms | int? | 是 | - | 时间戳毫秒 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：无

---

#### 52 LDI生产日志记录表 ( TBL_EAP_LDI_LOG )
- **业务含义**：包含了LDI的生产记录数据
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CDATETIME_CREATED | DateTime | 否 | - | 创建时间 |
| CDRY_FILM | string | 是 | - | 干膜参数 |
| CEND_TIME | string | 是 | - | 结束时间 |
| CEXPOSURE | string | 是 | - | 曝光参数 |
| CFACE | string | 是 | - | 面别 |
| CFLOOR | string | 是 | - | 层别 |
| CITEM_NO | string | 是 | - | 料号，对应TBL_BD_ITEM.CITEM_NO |
| CJOB_NAME | string | 是 | - | 作业名称 |
| CLAYER_NAME | string | 是 | - | 层名称 |
| CMACHINE_CODE | string | 是 | - | 设备代码 |
| CORDER_NO | string | 是 | - | 工单号，对应TBL_MO.CMO_LOT |
| CPE_THRESHOLD | string | 是 | - | PE阈值 |
| CSCALE_MODE | string | 是 | - | 缩放模式 |
| CSCALE_X | string | 是 | - | X方向缩放 |
| CSCALE_Y | string | 是 | - | Y方向缩放 |
| CSTART_TIME | string | 是 | - | 开始时间 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAP_LDI_LOG.CITEM_NO = TBL_BD_ITEM.CITEM_NO
  - TBL_EAP_LDI_LOG.CORDER_NO = TBL_MO.CMO_LOT

---

#### 53 LDI参数 ( TBL_EAP_LDI_PARAM )
- **业务含义**：包含LDI生产参数下发配方的配置信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CAB | string | 是 | - | AB板 |
| CBOARD_LENGTH | decimal? | 是 | - | 板长 |
| CBOARD_THICKNESS | decimal? | 是 | - | 板厚 |
| CBOARD_WIDTH | decimal? | 是 | - | 板宽 |
| CBOT_ALIGNMENT_LAYER | string | 是 | - | BOT对位层 |
| CBOT_LAYER | string | 是 | - | BOT层 |
| CCONTAINS_COPPER | string | 是 | - | 是否含铜 |
| CCOPPER_THICKNESS | string | 是 | - | 板材铜厚 |
| CDRY_FILM_NAME | string | 是 | - | 干膜名称 |
| CEXPANSION_X | decimal? | 是 | - | 涨缩系数X |
| CEXPANSION_Y | decimal? | 是 | - | 涨缩系数Y |
| CISSUED_MESSAGE | string | 是 | - | 下发失败消息 |
| CISSUED_RESULT | string | 是 | - | 下发结果 |
| CITEM_NO | string | 是 | - | 料号，对应TBL_BD_ITEM.CITEM_NO |
| CPART_NUM | string | 是 | - | 制造部件 |
| CREMARK | string | 是 | - | 备注 |
| CSTATUS | int | 否 | - | 状态，1：可用；0：不可用 |
| CTGZ_FILE_PATH | string | 是 | - | tgz文件地址 |
| CTOP_ALIGNMENT_LAYER | string | 是 | - | TOP对位层 |
| CTOP_LAYER | string | 是 | - | TOP层 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAP_LDI_PARAM.CITEM_NO = TBL_BD_ITEM.CITEM_NO

---

#### 54 班通检测主记录表 ( TBL_EAP_LWT_DETECTIONS )
- **业务含义**：包含班通线宽测量仪上传的测量记录主体信息
- **所属数据库**：192.168.49.18.CIEAP
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CDATETIME_CREATED | DateTime? | 是 | - | 创建时间 |
| CDATETIME_MODIFIED | DateTime? | 是 | - | 修改时间 |
| CDEVICE_ID | int? | 是 | - | 设备ID， 对应TBL_EAP_DEVICE.CDEVICE_ID |
| CDEVICE_NAME | string | 是 | - | 设备名称 |
| CID_NO | string | 是 | - | 标识编号 |
| CITEM | string | 是 | - | 检测项目 |
| CLAYER | string | 是 | - | 层别 |
| CLOT_NO | string | 是 | - | 工单号，对应TBL_MO.CMO_LOT |
| CMAX_VALUE | decimal? | 是 | - | 最大值 |
| CMIN_VALUE | decimal? | 是 | - | 最小值 |
| CSTAND_VALUE | decimal? | 是 | - | 标准值 |
| CID | long | 否 | - | 主键ID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAP_LWT_DETECTIONS.CDEVICE_ID = TBL_EAP_DEVICE.CDEVICE_ID
  - TBL_EAP_LWT_DETECTIONS.CLOT_NO = TBL_MO.CMO_LOT
  - TBL_EAP_LWT_DETECTIONS.CID = TBL_EAP_LWT_DETECTIONS_DTL.CMAIN_ID

---

#### 55 班通检测明细记录表 ( TBL_EAP_LWT_DETECTIONS_DTL )
- **业务含义**：包含班通线宽测量仪上传的测量记录项目明细信息
- **所属数据库**：192.168.49.18.CIEAP
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CDATETIME_CREATED | DateTime? | 是 | - | 创建时间 |
| CDATETIME_MODIFIED | DateTime? | 是 | - | 修改时间 |
| CIMAGE_DATA | string | 是 | - | 图片数据 |
| CIMAGE_NAME | string | 是 | - | 图片名称 |
| CIMAGE_PATH | string | 是 | - | 图片路径 |
| CIMAGE_SIZE | int? | 是 | - | 图片大小 |
| CIMAGE_TYPE | string | 是 | - | 图片类型 |
| CITEM | string | 是 | - | 检测项目 |
| CITEM_CODE | string | 是 | - | 项目编码 |
| CMAIN_ID | long | 否 | - | 主表ID，对应TBL_EAP_LWT_DETECTIONS.CID |
| CMAX_VALUE | decimal? | 是 | - | 最大值 |
| CMIN_VALUE | decimal? | 是 | - | 最小值 |
| CNUMBER | string | 是 | - | 序号 |
| CREAL_VALUE | decimal? | 是 | - | 实测值 |
| CREMARK | string | 是 | - | 备注 |
| CRESULT | string | 是 | - | 检测结果 |
| CSTAND_VALUE | decimal? | 是 | - | 标准值 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAP_LWT_DETECTIONS_DTL.CMAIN_ID = TBL_EAP_LWT_DETECTIONS.CID

---

#### 56 麦逊检测结果主表 ( TBL_EAP_MASON_DETECTIONS )
- **业务含义**：包含麦逊设备上传的检测记录主体信息
- **所属数据库**：192.168.49.18.CIEAP
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CCOUNT | int | 否 | - | 上传记录数 |
| CDATETIME_CREATED | DateTime | 否 | - | 创建时间 |
| CDATETIME_MODIFIED | DateTime? | 是 | - | 修改时间 |
| CMACHINE_NO | string | 是 | - | 设备编码 |
| CUSER_NO | string? | 是 | - | 用户编号 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAP_MASON_DETECTIONS.CID = TBL_EAP_MASON_DETECTIONS_DTL.CMAIN_ID

---

#### 57 麦逊检测结果明细表 ( TBL_EAP_MASON_DETECTIONS_DTL )
- **业务含义**：包含麦逊设备上传的测量记录项目明细信息
- **所属数据库**：192.168.49.18.CIEAP
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CBATCH_NO | string | 是 | - | 批次号 |
| CDATETIME_CREATED | DateTime | 否 | - | 创建时间 |
| CDATETIME_MODIFIED | DateTime? | 是 | - | 修改时间 |
| CDETECT_DATE | DateTime | 否 | - | 检测时间 |
| CDETECT_RESULT | string | 是 | - | 检测结果 |
| CDETECT_STEP | string | 是 | - | 检测步骤 |
| CIR | decimal | 否 | - | IR值 |
| CITEM_NO | string | 是 | - | 料号，对应TBL_BD_ITEM.CITEM_NO |
| CLOT_NO | string | 是 | - | 工单号，对应TBL_MO.CMO_LOT |
| CMAIN_ID | long | 否 | - | 主表ID |
| CNG_MESSAGE | string | 是 | - | NG信息（坏点信息） |
| CNG_SEQ | string | 是 | - | NG序号 |
| CPCB_NO | string | 是 | - | PCB编号 |
| CQR_CODE | string | 是 | - | 二维码 |
| CRDSON | decimal | 否 | - | RDSON值 |
| CREMARK | string | 是 | - | 备注 |
| CTOTAL_POINT | int | 否 | - | 总测点数 |
| CWEB_STRUCT | string | 是 | - | 网结构 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAP_MASON_DETECTIONS_DTL.CMAIN_ID = TBL_EAP_MASON_DETECTIONS.CID
  - TBL_EAP_MASON_DETECTIONS_DTL.CLOT_NO = TBL_MO.CMO_LOT
  - TBL_EAP_MASON_DETECTIONS_DTL.CITEM_NO = TBL_BD_ITEM.CITEM_NO

---

#### 58 图形电镀检测主记录表 ( TBL_EAP_PATTERN_PLAT )
- **业务含义**：包含图形电镀设备上传的检测记录主体信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CCOPPER_HOLE | double | 否 | - | 铜孔 |
| CCUSTOMER_NO | string | 是 | - | 客户代码 |
| CDAY | DateTime? | 是 | - | 日期 |
| CFILE_NAME | string | 是 | - | 文件名称 |
| CITEM_NO | string | 是 | - | 生产编号，对应TBL_BD_ITEM.CITEM_NO |
| CPROCESS_ID | long? | 是 | - | 工序ID，对应TBL_BD_PROCESS.CID |
| CREMARK | string | 是 | - | 备注 |
| CRESULT | string? | 是 | - | 判定结果，ACC：合格；REJ：不合格 |
| CRESULT_MIN | double | 否 | - | 结果最小值 |
| CSHIFFT | string? | 是 | - | 班次 |
| CID | long | 否 | - | 主键ID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAP_PATTERN_PLAT.CITEM_NO = TBL_BD_ITEM.CITEM_NO
  - TBL_EAP_PATTERN_PLAT.CPROCESS_ID = TBL_BD_PROCESS.CID
  - TBL_EAP_PATTERN_PLAT.CID = TBL_EAP_PATTERN_PLAT_ITEM.CPATTERN_PLAT_ID

---

#### 59 图形电镀检测明细表 ( TBL_EAP_PATTERN_PLAT_ITEM )
- **业务含义**：包含图形电镀设备上传的检测记录项目明细信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CPATTERN_PLAT_ID | long | 否 | - | 主表ID，对应TBL_EAP_PATTERN_PLAT.CID |
| CRESULT_DATA_1 | double? | 是 | - | 检测值1 |
| CRESULT_DATA_2 | double? | 是 | - | 检测值2 |
| CRESULT_DATA_3 | double? | 是 | - | 检测值3 |
| CRESULT_DATA_4 | double? | 是 | - | 检测值4 |
| CRESULT_DATA_5 | double? | 是 | - | 检测值5 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAP_PATTERN_PLAT_ITEM.CPATTERN_PLAT_ID = TBL_EAP_PATTERN_PLAT.CID

---

#### 60 设备状态时段记录表 ( TBL_EAP_PERIOD )
- **业务含义**：记录每个设备的状态发生变化的开始时间到结束时间
- **所属数据库**：192.168.49.10.CIEAP、192.168.49.18.CIEAP
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CDATETIME_CREATED | DateTime | 否 | - | 创建时间 |
| CDATETIME_MODIFIED | DateTime? | 是 | - | 修改时间 |
| CDEVICE_ID | int | 否 | - | 设备ID， 对应TBL_EAP_DEVICE.CDEVICE_ID |
| CEND_TIME | DateTime? | 是 | - | 时段结束时间 |
| CIS_END | char | 否 | - | 是否已结束 |
| CSTART_TIME | DateTime | 否 | - | 时段开始时间 |
| CSTATUS | int | 否 | - | 状态码 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAP_PERIOD.CDEVICE_ID = TBL_EAP_DEVICE.CDEVICE_ID

---

#### 61 汉印喷印机内容配置表 ( TBL_EAP_PMS_CONTENT )
- **业务含义**：包含汉印喷印机的下发喷印内容的数据配置信息
- **所属数据库**：192.168.49.10.CIEAP
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CCONTENT | string | 是 | - | 内容 |
| CDATETIME_CREATED | DateTime? | 是 | - | 创建时间 |
| CDATETIME_MODIFIED | DateTime? | 是 | - | 修改时间 |
| CDEVICE_ID | int? | 是 | - | 设备ID， 对应TBL_EAP_DEVICE.CDEVICE_ID |
| CITEM_NO | string | 是 | - | 料号，对应TBL_BD_ITEM.CITEM_NO |
| CLABEL_H | decimal? | 是 | - | 标签高度 |
| CLABEL_W | decimal? | 是 | - | 标签宽度 |
| CLAYER | string | 是 | - | 层别 |
| CPOSITION_CONTER_X | decimal? | 是 | - | 中心点X坐标 |
| CPOSITION_CONTER_Y | decimal? | 是 | - | 中心点Y坐标 |
| CPOSITION_X | decimal? | 是 | - | X坐标 |
| CPOSITION_Y | decimal? | 是 | - | Y坐标 |
| CREF_ID | string? | 是 | - | 关联编号 |
| CREMARK | string | 是 | - | 备注 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAP_PMS_CONTENT.CDEVICE_ID = TBL_EAP_DEVICE.CDEVICE_ID
  - TBL_EAP_PMS_CONTENT.CITEM_NO = TBL_BD_ITEM.CITEM_NO

---

#### 62 汉印生产记录主表 ( TBL_EAP_PMS_PROD )
- **业务含义**：包含汉印喷印机上传的生产记录主体信息
- **所属数据库**：192.168.49.10.CIEAP
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CDATETIME_CREATED | DateTime? | 是 | - | 创建时间 |
| CDATETIME_MODIFIED | DateTime? | 是 | - | 修改时间 |
| CDEVICE_ID | int? | 是 | - | 设备ID， 对应TBL_EAP_DEVICE.CDEVICE_ID |
| CFACE | string | 是 | - | 面别 |
| CID | long | 否 | - | 主键ID |
| CPNL_CODE | string | 是 | - | PNL条码 |
| CRESULT | string | 是 | - | 结果 |
| CWON | string | 是 | - | 工单号，对应TBL_MO.CMO_LOT |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAP_PMS_PROD.CDEVICE_ID = TBL_EAP_DEVICE.CDEVICE_ID
  - TBL_EAP_PMS_PROD.CWON = TBL_MO.CMO_LOT
  - TBL_EAP_PMS_PROD.CID = TBL_EAP_PMS_PROD_DTL.CPROD_ID

---

#### 63 汉印生产记录明细表 ( TBL_EAP_PMS_PROD_DTL )
- **业务含义**：包含汉印喷印机上传的生产记录项目明细信息
- **所属数据库**：192.168.49.10.CIEAP
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CCONTENT | string | 是 | - | 内容 |
| CDATETIME_CREATED | DateTime? | 是 | - | 创建时间 |
| CDATETIME_MODIFIED | DateTime? | 是 | - | 修改时间 |
| CID | long | 否 | - | 主键ID |
| CPROD_ID | long? | 是 | - | 主表ID，对应TBL_EAP_PMS_PROD.CID |
| CREF_ID | int | 否 | - | 关联编号 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAP_PMS_PROD_DTL.CPROD_ID = TBL_EAP_PMS_PROD.CID

---

#### 64 放板机关机记录表 ( TBL_EAP_SHUTDOWN_RECORD )
- **业务含义**：包含所有放板机的掉线记录日志
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CDEVICE_NAME | string | 是 | - | 设备名称 |
| CLOGIN_USER | string | 是 | - | 登录用户 |
| CMSG | string | 是 | - | 消息内容 |
| CMSG_TYPE | string | 是 | - | 消息类型 |
| CREMARK | string | 是 | - | 备注 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAP_SHUTDOWN_RECORD.CLOGIN_USER = TBL_SYS_USER.CUSER_NAME

---

#### 65 设备状态采集记录表 ( TBL_EAP_STATUS )
- **业务含义**：包含了在边缘网关中联机的设备的运行状态的实时采集数值
- **所属数据库**：192.168.49.10.CIEAP、192.168.49.18.CIEAP
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CDEVICE_ID | int | 否 | - | 设备ID， 对应TBL_EAP_DEVICE.CDEVICE_ID |
| CDURATION | decimal | 否 | - | 持续时长 |
| CEXTRA | string | 是 | - | 扩展信息 |
| CFILE_NAME | string | 是 | - | 来源文件名 |
| CITEM_NO | string | 是 | - | 料号 |
| CLOT | string | 是 | - | 批次号 |
| CMACHINE_NAME | string | 是 | - | 设备名称 |
| CMACHINE_TIME | DateTime | 否 | - | 设备时间 |
| CMACHINE_USER | string | 是 | - | 操作用户 |
| CMANUAL_STATUS | int | 否 | - | 手动状态码 |
| COEE | decimal | 否 | - | OEE值 |
| CPROGRESS | decimal | 否 | - | 进度 |
| CQTY | decimal | 否 | - | 数量 |
| CREMARK | string | 是 | - | 备注 |
| CSTATUS | int | 否 | - | 状态码 |
| CSTATUS_START_TIME | DateTime | 否 | - | 状态开始时间 |
| CTEXT | string | 是 | - | 文本内容 |
| CUNIT_STATUS | string | 是 | - | 机台状态文本 |
| CVERSION | string | 是 | - | 版本 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAP_STATUS.CDEVICE_ID = TBL_EAP_DEVICE.CDEVICE_ID

---

#### 66 测点配置表 ( TBL_EAP_TAG )
- **业务含义**：包含了在边缘网关中联机的设备的所有测点的配置信息
- **所属数据库**：192.168.49.10.CIEAP、192.168.49.18.CIEAP
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CDATETIME_CREATED | DateTime | 否 | - | 创建时间 |
| CDATETIME_MODIFIED | DateTime | 否 | - | 修改时间 |
| CDEVICE_ID | int? | 是 | - | 设备ID， 对应TBL_EAP_DEVICE.CDEVICE_ID |
| CDEVICE_NAME | string | 是 | - | 设备描述 |
| CDEVICE_SERIAL | short? | 是 | - | 设备序号 |
| CENTERPRISE_CODE | string | 是 | - | 企业编码 |
| CGROUP_NAME | string | 是 | - | 类别名称 |
| CGROUP_SERIAL | short | 否 | - | 类别序号 |
| CID | long | 否 | - | 主键ID |
| CINSTANCE_ID | string | 是 | - | 实例ID |
| CMAX_VALUE | decimal? | 是 | - | 最大值 |
| CMIN_VALUE | decimal? | 是 | - | 最小值 |
| CORG_CODE | string | 是 | - | 组织编码 |
| CRADIX | int | 否 | - | 进制 |
| CROWREMARK | string | 是 | - | 行备注 |
| CSEQ | int | 否 | - | 排序号 |
| CSERVER_ID | string | 是 | - | 服务器ID |
| CSERVER_NAME | string | 是 | - | 服务器名称 |
| CSERVER_SERIAL | int | 否 | - | 服务器序号 |
| CSHOW_TYPE | string | 是 | - | 显示类型 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
| CTAG_ALIAS | string | 是 | - | 参数别名 |
| CTAG_DESC | string | 是 | - | 参数描述 |
| CTAG_ID | int | 否 | - | 测点ID |
| CTAG_NAME | string | 是 | - | 参数集名称 |
| CTAG_PATH | string | 是 | - | 参数路径 |
| CTAG_SERIAL | short | 否 | - | 测点序号 |
| CUNIT | string | 是 | - | 单位 |
| CUSER_CREATED | string | 是 | - | 创建用户 |
| CUSER_MODIFIED | string | 是 | - | 修改用户 |
- **关联关系**：
  - TBL_EAP_TAG.CDEVICE_ID = TBL_EAP_DEVICE.CDEVICE_ID
  - TBL_EAP_TAG.CTAG_ID = TBL_EAP_CURRENT_DATA.CTAG_ID
  - TBL_EAP_TAG.CTAG_ID = TBL_EAP_DATA_YYYYMM.CTAG_ID
  - TBL_EAP_TAG.CTAG_ID = TBL_EAP_ALARM_CONTROL_LINK.CTAG_ID

---

#### 67 三次元数据 ( TBL_EAP_THREE_D_DATA )
- **业务含义**：包含三次元设备上传的测量数据信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CA | decimal? | 是 | - | A参数 |
| CAVERAGE_VALUE | double? | 是 | - | 平均值 |
| CDATETIME_CREATED | DateTime | 否 | - | 创建时间 |
| CDATETIME_MODIFIED | DateTime | 否 | - | 修改时间 |
| CDAY | DateTime? | 是 | - | 日期 |
| CDEVIATION | decimal? | 是 | - | 标准差 |
| CID | long | 否 | - | 主键ID |
| CITEM | string | 是 | - | 项目名称 |
| CLOW_TOLERANCE | double | 否 | - | 下公差 |
| CMAX_VALUE | decimal? | 是 | - | 最大值 |
| CMEASURE_VALUE | double | 否 | - | 测量值 |
| CMIN_VALUE | decimal? | 是 | - | 最小值 |
| CMISCOUNT | double | 否 | - | 误差 |
| CP | decimal? | 是 | - | 过程能力指数P |
| CPK | decimal? | 是 | - | 过程能力指数CPK |
| CRECORD_ID | long | 否 | - | 记录ID，对应TBL_EAP_THREE_D_RECORD.CID |
| CRESULT | string | 是 | - | 判定，OK：合格；NG：不合格 |
| CSAMPLE_COUNT | int? | 是 | - | 样本大小 |
| CSHIFFT | string? | 是 | - | 班次 |
| CSTANDARD | double | 否 | - | 标准值 |
| CTYPE | string | 是 | - | 型式 |
| CUNIT | string | 是 | - | 单位 |
| CUP_TOLERANCE | double | 否 | - | 上公差 |
| CUSER_CREATED | string | 是 | - | 创建人 |
| CUSER_MODIFIED | string | 是 | - | 修改人 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAP_THREE_D_DATA.CRECORD_ID = TBL_EAP_THREE_D_RECORD.CID

---

#### 68 三次元数据明细 ( TBL_EAP_THREE_D_ITEM )
- **业务含义**：包含三次元设备上传的测量数据项目明细信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CDAY | DateTime? | 是 | - | 日期 |
| CDEVICE_ID | long | 否 | - | 项目分组ID |
| CDEVICE_NAME | string | 是 | - | 项目名称 |
| CDEVICE_SEQ | int | 否 | - | 项目序号 |
| CFILE_NAME | string | 是 | - | 文件路径 |
| CFLAG | int? | 是 | - | 标记位 |
| CLOW_TOLERANCE | double | 否 | - | 下公差 |
| CMEASURE_VALUE | double | 否 | - | 测量值 |
| CMISCOUNT | double | 否 | - | 误差 |
| CRESULT | string | 是 | - | 判定，OK：合格；NG：不合格 |
| CSHIFFT | string? | 是 | - | 班次 |
| CSTANDARD | double | 否 | - | 标准值 |
| CUP_TOLERANCE | double | 否 | - | 上公差 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：无

---

#### 69 三次元文件记录主表 ( TBL_EAP_THREE_D_RECORD )
- **业务含义**：包含三次元设备上传的测量数据信息的日志
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CDATETIME_CREATED | DateTime | 否 | - | 创建时间 |
| CDATETIME_MODIFIED | DateTime | 否 | - | 修改时间 |
| CDAY | DateTime? | 是 | - | 日期 |
| CFILE_NAME | string | 是 | - | 文件路径 |
| CID | long | 否 | - | 主键ID |
| CPROCESS_ID | long? | 是 | - | 工序ID，对应TBL_BD_PROCESS.CID |
| CSHIFFT | string? | 是 | - | 班次 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAP_THREE_D_RECORD.CPROCESS_ID = TBL_BD_PROCESS.CID
  - TBL_EAP_THREE_D_RECORD.CID = TBL_EAP_THREE_D_DATA.CRECORD_ID

---

#### 70 放板机时间范围管控 ( TBL_EAP_TIME_RANGE_CONTROL )
- **业务含义**：描述了放板机的禁止运行时间的配置情况
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CEND_TIME | TimeSpan? | 是 | - | 禁止运行结束时间 |
| CFREQUENCY | string | 是 | - | 生效频率 |
| CPARENT_DEVICE | string | 是 | - | 父设备标识 |
| CSTART_TIME | TimeSpan? | 是 | - | 禁止运行开始时间 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：无

---

#### 71 誉汇测试记录主表 ( TBL_EAP_YUHUI_TEST_RECORDS )
- **业务含义**：包含誉汇测试机设备上传的测试数据主体信息
- **所属数据库**：192.168.49.18.CIEAP
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CBOARD_COUNT | int | 否 | - | 板数量 |
| CBOARD_TYPE | string | 是 | - | 板类型 |
| CDATETIME_CREATED | DateTime? | 是 | - | 创建时间 |
| CDATETIME_MODIFIED | DateTime? | 是 | - | 修改时间 |
| CDEVICE_ID | int? | 是 | - | 设备ID， 对应TBL_EAP_DEVICE.CDEVICE_ID |
| CDEVICE_NAME | string | 是 | - | 设备名称 |
| CID | long | 否 | - | 主键ID |
| CITEM_NO | string | 是 | - | 料号，对应TBL_BD_ITEM.CITEM_NO |
| CORDER_NO | string | 是 | - | 工单号，对应TBL_MO.CMO_LOT |
| CTEST_TIME | DateTime? | 是 | - | 检测时间 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAP_YUHUI_TEST_RECORDS.CDEVICE_ID = TBL_EAP_DEVICE.CDEVICE_ID
  - TBL_EAP_YUHUI_TEST_RECORDS.CITEM_NO = TBL_BD_ITEM.CITEM_NO
  - TBL_EAP_YUHUI_TEST_RECORDS.CORDER_NO = TBL_MO.CMO_LOT
  - TBL_EAP_YUHUI_TEST_RECORDS.CID = TBL_EAP_YUHUI_TEST_RECORDS_DTL.CMAIN_ID

---

#### 72 誉汇测试记录明细表 ( TBL_EAP_YUHUI_TEST_RECORDS_DTL )
- **业务含义**：包含誉汇测试机设备上传的测试数据项目明细信息
- **所属数据库**：192.168.49.18.CIEAP
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CAREA | string | 是 | - | 区域 |
| CBOARD_SEQ | string | 是 | - | 板序号 |
| CDATETIME_CREATED | DateTime? | 是 | - | 创建时间 |
| CDATETIME_MODIFIED | DateTime? | 是 | - | 修改时间 |
| CDOWN_BOUND | decimal? | 是 | - | 下限 |
| CERR_VALUE | decimal? | 是 | - | 误差值 |
| CID | long | 否 | - | 主键ID |
| CINNER_SEQ | int? | 是 | - | 板内序号 |
| CITEM | string | 是 | - | 量测项目 |
| CITEM_TYPE | string | 是 | - | 项目类型 |
| CMAIN_ID | long | 否 | - | 主表ID，对应TBL_EAP_YUHUI_TEST_RECORDS.CID |
| CN_TOL | decimal? | 是 | - | 负公差 |
| CP_TOL | decimal? | 是 | - | 正公差 |
| CPOSITION_END | string | 是 | - | 结束位置 |
| CPOSITION_START | string | 是 | - | 起始位置 |
| CREAL_VALUE | decimal? | 是 | - | 实测值 |
| CRESULT | string | 是 | - | 检测结果 |
| CSTAND_VALUE | decimal? | 是 | - | 标准值 |
| CUNIT | string | 是 | - | 单位 |
| CUP_BOUND | decimal? | 是 | - | 上限 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAP_YUHUI_TEST_RECORDS_DTL.CMAIN_ID = TBL_EAP_YUHUI_TEST_RECORDS.CID

---

#### 73 锁机锁卡异常数据表 ( TBL_ABNORMAL_DATA_POOL )
- **业务含义**：包含触发锁机锁卡条件的异常数据，在进行确认后会进行删除
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CABNORMAL_TYPE | string | 是 | - | 异常类型 |
| CDEVICE_NAME | string | 是 | - | 设备名(可空) |
| CFOREIGN_KEY_ID | long? | 是 | - | 外键ID |
| CFOREIGN_TABLE | string | 是 | - | 外键对应的表 |
| CIDENTIFY_FIELD | string | 是 | - | 校验识别字段 |
| CREMARK | string | 是 | - | 备注 |
| CTEMPLATE_ITEM_NAME | string | 是 | - | 模板项目名(可空) |
| CTEMPLATE_NAME | string | 是 | - | 模板名(可空) |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：无

---

#### 74 浩硕图形电镀生产记录主表 ( TBL_PATTERN_HAOSHUO_PRODUCTION_RECORD )
- **业务含义**：包含浩硕图形电镀设备上传的生产记录主体信息
- **所属数据库**：192.168.49.18.CIEAP
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CBARCODE | string | 是 | - | 板边码 |
| CDEFECTS | string | 是 | - | XY明细坐标 |
| CID | long | 否 | - | 主键ID |
| CITEM_NO | string | 是 | - | 料号，对应TBL_BD_ITEM.CITEM_NO |
| CLOT_NO | string? | 是 | - | 工单，对应TBL_MO.CMO_LOT |
| CMACHINE_CODE | string | 是 | - | 设备代码 |
| CPRODUCTION_END_TIME | string | 是 | - | 打靶完成时间 |
| CPRODUCTION_START_TIME | string | 是 | - | 开始打靶时间 |
| CUSER_CREATED | string | 是 | - | 人员，对应TBL_SYS_USER.CUSER_NAME |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_PATTERN_HAOSHUO_PRODUCTION_RECORD.CITEM_NO = TBL_BD_ITEM.CITEM_NO
  - TBL_PATTERN_HAOSHUO_PRODUCTION_RECORD.CLOT_NO = TBL_MO.CMO_LOT
  - TBL_PATTERN_HAOSHUO_PRODUCTION_RECORD.CUSER_CREATED = TBL_SYS_USER.CUSER_NAME
  - TBL_PATTERN_HAOSHUO_PRODUCTION_RECORD.CID = TBL_PATTERN_HAOSHUO_PRODUCTION_RECORD_DTL.CDETECTION_ID

---

#### 75 浩硕图形电镀生产记录明细表 ( TBL_PATTERN_HAOSHUO_PRODUCTION_RECORD_DTL )
- **业务含义**：包含浩硕图形电镀设备上传的生产记录明细信息
- **所属数据库**：192.168.49.18.CIEAP
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CCORDINATE_X | string | 是 | - | X涨缩 |
| CCORDINATE_Y | string | 是 | - | Y涨缩 |
| CDATETIME_CREATED | DateTime? | 是 | - | 创建时间 |
| CDATETIME_MODIFIED | DateTime? | 是 | - | 修改时间 |
| CDETECTION_ID | long | 否 | - | 主表CID，对应TBL_PATTERN_HAOSHUO_PRODUCTION_RECORD.CID |
| CID | long | 否 | - | 主键ID |
| CMACHINE_CODE | string | 是 | - | 设备代码 |
| CRESULT | string | 是 | - | 判定结果 |
| CSTAN_X | decimal? | 是 | - | X标准值 |
| CSTAN_Y | decimal? | 是 | - | Y标准值 |
| DISTANCE_X | string | 是 | - | X坐标 |
| DISTANCE_Y | string | 是 | - | Y坐标 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_PATTERN_HAOSHUO_PRODUCTION_RECORD_DTL.CDETECTION_ID = TBL_PATTERN_HAOSHUO_PRODUCTION_RECORD.CID

---

### 2.5 品质管理

> 本章节数据来源于 Excel 工作表：`品质管理`

#### 76 化验任务记录表 ( TBL_QM_ASSAY_LOG )
- **业务含义**：包含了由定时程序定时生成的药水化验任务
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CASSAY_RESULT | int | 否 | - | 化验结果：1：正常、2：异常 |
| CASSAY_STATUS | int | 否 | - | 化验状态：1：已化验、0：未化验 |
| CASSAY_TIME | DateTime? | 是 | - | 化验时间 |
| CASSAY_USER | string | 是 | - | 化验人，对应TBL_SYS_USER.CUSER_NAME |
| CBASE_TASK_NO | string | 是 | - | 基础任务编号 |
| CCHECK_REMARK | string | 是 | - | 审核备注 |
| CCHECK_STATUS | int | 否 | - | 审核状态1：已审核、0：未审核 |
| CCHECK_TIME | DateTime? | 是 | - | 审核时间 |
| CCHECK_USER | string | 是 | - | 审核人，对应TBL_SYS_USER.CUSER_NAME |
| CIS_OPEN_LINE | string | 是 | - | 是否开线前分析，Y:是；N:否 |
| CMEDICINE_TANK_ID | long | 否 | - | 药缸ID，对应TBL_QM_MEDICINE_TANK.CID |
| CRECEIVE_TIME | DateTime? | 是 | - | 接收时间 |
| CRECEIVE_USER | string | 是 | - | 接收人，对应TBL_SYS_USER.CUSER_NAME |
| CREMARK | string | 是 | - | 备注 |
| CSAMPLE_BARCODE | string | 是 | - | 样品条码 |
| CSAMPLE_REMARK | string | 是 | - | 取样备注 |
| CSAMPLE_TIME | DateTime? | 是 | - | 取样时间 |
| CSAMPLE_USER | string | 是 | - | 取样人，对应TBL_SYS_USER.CUSER_NAME |
| CSHIFT | string | 是 | - | 班次 |
| CTASK_NO | string | 是 | - | 任务编号 |
| CTASK_STAND_TIME_E | DateTime? | 是 | - | 任务标准结束时间 |
| CTASK_STAND_TIME_S | DateTime? | 是 | - | 任务标准开始时间 |
| CTASK_STATUS | int | 否 | - | 任务状态：1：已执行、0：未执行 |
| CTASK_TAG | string | 是 | - | 任务标签 |
| CTASK_TYPE | int | 否 | - | 任务类型 |
| CWC_ID | long | 否 | - | 工作中心ID，对应TBL_BD_WC.CID |
| CID | long | 否 | - | 主键 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_QM_ASSAY_LOG.CWC_ID = TBL_BD_WC.CID
  - TBL_QM_ASSAY_LOG.CMEDICINE_TANK_ID = TBL_QM_MEDICINE_TANK.CID
  - TBL_QM_ASSAY_LOG.CASSAY_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_QM_ASSAY_LOG.CCHECK_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_QM_ASSAY_LOG.CRECEIVE_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_QM_ASSAY_LOG.CSAMPLE_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_QM_ASSAY_LOG.CID = TBL_QM_ASSAY_LOG_ITEM.CASSAY_LOG_ID

---

#### 77 化验任务明细表 ( TBL_QM_ASSAY_LOG_ITEM )
- **业务含义**：包含了由定时程序定时生成的药水化验任务的化验项目明细信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CALARM_MAX_VALUE | decimal? | 是 | - | 预警值上限 |
| CALARM_MIN_VALUE | decimal? | 是 | - | 预警值下限 |
| CASSAY_LOG_ID | long | 否 | - | 化验主表ID，对应TBL_QM_ASSAY_LOG.CID |
| CCHECK_WAY | int? | 是 | - | 校验方式 |
| CCORRECTIVE_ACTION | string | 是 | - | 纠正措施 |
| CDATETIME_CREATED | DateTime? | 是 | - | 创建时间 |
| CDATETIME_MODIFIED | DateTime? | 是 | - | 修改时间 |
| CEND_VALUE | string | 是 | - | 终值 |
| CENTERPRISE_CODE | long? | 是 | - | 企业代码 |
| CFORMULA | string | 是 | - | 补加量公式 |
| CINPUT_FORMULA | string | 是 | - | 结果值计算公式 |
| CINPUT_TYPE | int? | 是 | - | 录入框类型 |
| CINPUT_VALUE | string? | 是 | - | 录入值 |
| CINSTANCE_ID | string | 是 | - | 实例ID |
| CIS_CHECK_RESULT | string | 是 | - | 是否校验，Y：是；N：否 |
| CIS_CONFIRM | int? | 是 | - | 是否已确认添加，Y：是；N：否 |
| CIS_MUST | string | 是 | - | 是否必填，Y：是；N：否 |
| CITEM_FREQ_ID | long? | 是 | - | 任务频率ID，对应TBL_EAM_FREQUENCY.CID |
| CLIST_SOURCE | string | 是 | - | 下拉框数据源 |
| CLIST_SOURCE_TYPE | int? | 是 | - | 下拉框数据源类型 |
| CORG_CODE | long? | 是 | - | 组织代码 |
| CPROCESS_INFO | string | 是 | - | 原因分析 |
| CREMARK | string | 是 | - | 备注 |
| CREPLENISHMENT | string | 是 | - | 补加量 |
| CRESULT | int? | 是 | - | 结果：0：不合格、1：合格 |
| CRETEST_RESULT | int? | 是 | - | 复测结果：0：不合格、1：合格 |
| CRETEST_TIME | DateTime? | 是 | - | 复测时间 |
| CRETEST_USER | string | 是 | - | 复测人，对应TBL_SYS_USER.CUSER_NAME |
| CRETEST_VALUE | string | 是 | - | 复测值 |
| CROWREMARK | string | 是 | - | 行备注 |
| CSEQ | int? | 是 | - | 顺序号 |
| CSTANDARD_MAX_ALLOW | string | 是 | - | 是否允许等于上限，Y：是；N：否 |
| CSTANDARD_MAX_VALUE | decimal? | 是 | - | 标准值上限 |
| CSTANDARD_MIN_ALLOW | string | 是 | - | 是否允许等于下限，Y：是；N：否 |
| CSTANDARD_MIN_VALUE | decimal? | 是 | - | 标准值下限 |
| CSTANDARD_VALUE | string | 是 | - | 标准值 |
| CSTANDARD_VALUE_TYPE | int? | 是 | - | 标准值类型 |
| CSTART_VALUE | string | 是 | - | 始值 |
| CTEMPLATE_ITEM_CODE | string | 是 | - | 项目编码 |
| CTEMPLATE_ITEM_DESC | string | 是 | - | 项目描述 |
| CTEMPLATE_ITEM_NAME | string | 是 | - | 项目名称 |
| CTEMPLATE_ITEM_TAG | string | 是 | - | 项目标签 |
| CTITRATION_VALUE | string | 是 | - | 滴定值 |
| CUNIT | string | 是 | - | 单位 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_QM_ASSAY_LOG_ITEM.CASSAY_LOG_ID = TBL_QM_ASSAY_LOG.CID
  - TBL_QM_ASSAY_LOG_ITEM.CRETEST_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_QM_ASSAY_LOG_ITEM.CITEM_FREQ_ID = TBL_EAM_FREQUENCY.CID

---

#### 78 客诉异常报告信息表 ( TBL_QM_CC_EXCEPTION )
- **业务含义**：包含客户对产品质量问题投诉报告的信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CAUDIT_MAN | string | 是 | - | 审核人，对应TBL_SYS_USER.CUSER_NAME |
| CAUDIT_TIME | DateTime? | 是 | - | 审核时间 |
| CBAD_QTY | decimal? | 是 | - | 不良数量 |
| CBAD_RATIO | string | 是 | - | 不良比例 |
| CBAD_TYPE | string | 是 | - | 不良类型 |
| CCHECK_USER | string | 是 | - | 检查人，对应TBL_SYS_USER.CUSER_NAME |
| CCOMPLAINT_LEVEL | string | 是 | - | 客诉等级 |
| CCUR_PROCESS | int? | 是 | - | 当前流程 |
| CCUSTOMER_MODEL | string | 是 | - | 客户型号 |
| CCUSTOMER_NO | string | 是 | - | 客户代码 |
| CDATA_TYPE | int | 否 | - | 数据类型 |
| CDUTY_PROCESS_ID | long? | 是 | - | 责任工序ID, TBL_BD_PROCESS表CID |
| CDUTY_PROCESS_USER | string | 是 | - | 责任工序责任人 |
| CEFFECT_VERIFICATION | string | 是 | - | 效果验证 |
| CEXCEP_CODE | string | 是 | - | 报告编号 |
| CEXCEP_DESC | string | 是 | - | 异常描述 |
| CEXCEP_PROCESS_ID | long | 否 | - | 异常发生工序ID, TBL_BD_PROCESS表CID |
| CFEEDBACK_DATE | DateTime? | 是 | - | 反馈日期 |
| CIPQA_AUDIT_MAN | string | 是 | - | IPQA审核人 |
| CIPQA_AUDIT_REMARK | string | 是 | - | IPQA审核备注 |
| CIPQA_AUDIT_STATUS | int? | 是 | - | IPQA审核状态 |
| CIPQA_AUDIT_TIME | DateTime? | 是 | - | IPQA审核时间 |
| CIPQA_TIME | DateTime? | 是 | - | IPQA处理时间 |
| CIS_SYNC_CUSTOMER | string | 是 | - | 是否同步客户 |
| CITEM_ID | long? | 是 | - | 外键，产品或物料ID  对应 [TBL_BD_ITEM].[CID] |
| CITEM_NO | string | 是 | - | 产品型号，对应TBL_BD_ITEM.CITEM_NO |
| CMATERIAL_PLACE | string | 是 | - | 生产场所 |
| CNEED_DATE | DateTime? | 是 | - | 要求日期 |
| COCCUR_DATE | DateTime? | 是 | - | 发生时间 |
| COCCUR_PLACE | string | 是 | - | 发送地点 |
| COUT_CAUSE_STATUS | int | 否 | - | 流出原因分析状态 |
| COUT_IMPLEMENT_STATUS | int | 否 | - | 流出执行状态 |
| COUT_MEASURE_STATUS | int | 否 | - | 流出措施状态 |
| COUT_PROCESS_ID | long | 否 | - | 流出工序ID, TBL_BD_PROCESS表CID |
| COUT_PROCESS_USER | string | 是 | - | 流出工序责任人，对应TBL_SYS_USER.CUSER_NAME |
| CPREVENT_STATUS | int | 否 | - | 预防状态 |
| CPRO_CAUSE_STATUS | int | 否 | - | 生产原因分析状态 |
| CPRO_IMPLEMENT_STATUS | int | 否 | - | 生产执行状态 |
| CPRO_MEASURE_STATUS | int | 否 | - | 生产措施状态 |
| CPRODUCT_STAGE | int? | 是 | - | 产品阶段 |
| CRECEIVE_USER | string | 是 | - | 接收人，对应TBL_SYS_USER.CUSER_NAME |
| CREMARK | string | 是 | - | 备注 |
| CSHIPMENT_QTY | decimal? | 是 | - | 出货数量 |
| CSTATUS | int? | 是 | - | 状态：1待开始、2进行中、3已完成、4已退回 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_QM_CC_EXCEPTION.CITEM_ID = TBL_BD_ITEM.CID
  - TBL_QM_CC_EXCEPTION.CDUTY_PROCESS_ID = TBL_BD_PROCESS.CID
  - TBL_QM_CC_EXCEPTION.CEXCEP_PROCESS_ID = TBL_BD_PROCESS.CID
  - TBL_QM_CC_EXCEPTION.COUT_PROCESS_ID = TBL_BD_PROCESS.CID
  - TBL_QM_CC_EXCEPTION.CAUDIT_MAN = TBL_SYS_USER.CUSER_NAME
  - TBL_QM_CC_EXCEPTION.CCHECK_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_QM_CC_EXCEPTION.CRECEIVE_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_QM_CC_EXCEPTION.CITEM_NO = TBL_BD_ITEM.CITEM_NO
  - TBL_QM_CC_EXCEPTION.COUT_PROCESS_USER = TBL_SYS_USER.CUSER_NAME

---

#### 79 品质投诉记录表 ( TBL_QM_COMPLAINT )
- **业务含义**：包含客户对产品质量问题投诉的记录
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| C8D_NUMBER | string | 是 | - | 8D编号 |
| CAFFECTED_AMOUNT | string | 是 | - | 受影响金额 |
| CCOMPLAINT_DATE | DateTime? | 是 | - | 投诉日期 |
| CCOMPLAINT_TYPE | string | 是 | - | 客诉类型 |
| CCUSTOMER_CODE | string | 是 | - | 客户编码 |
| CCUSTOMER_MODEL | string | 是 | - | 客户型号 |
| CCYCLE | string | 是 | - | 周期 |
| CDEFECT_QUANTITY | int? | 是 | - | 不良数量 |
| CDEFECT_RATE | string | 是 | - | 不良比例 |
| CFABRIC_MODEL | string | 是 | - | 本厂型号 |
| CHANDLING_METHOD | string | 是 | - | 处理方式 |
| CIS_MP | bool | 否 | - | 是否生成防错计划（1：是，0：否） |
| COCCURRENCE_PROCESS | string | 是 | - | 发生工序，对应TBL_BD_PROCESS.CPROCESS_NAME |
| COUTFLOW_PROCESS | string | 是 | - | 流出工序，对应TBL_BD_PROCESS.CPROCESS_NAME |
| CPROBLEM_DESC | string | 是 | - | 问题描述 |
| CRESPONSIBLE_PERSON | string | 是 | - | 责任人，对应TBL_SYS_USER.CUSER_NAME |
| CRESPONSIBLE_UNIT | string | 是 | - | 责任单位 |
| CID | long | 否 | - | 主键 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_QM_COMPLAINT.CRESPONSIBLE_PERSON = TBL_SYS_USER.CUSER_NAME
  - TBL_QM_COMPLAINT.CID = TBL_QM_COMPLAINT_IMAGE.CCOMPLAINT_ID
  - TBL_QM_COMPLAINT.COCCURRENCE_PROCESS = TBL_BD_PROCESS.CPROCESS_NAME
  - TBL_QM_COMPLAINT.COUTFLOW_PROCESS = TBL_BD_PROCESS.CPROCESS_NAME

---

#### 80 品质投诉图片表 ( TBL_QM_COMPLAINT_IMAGE )
- **业务含义**：包含客户对产品质量问题投诉的记录的图片信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CCOMPLAINT_ID | long | 否 | - | 投诉记录ID  对应 TBL_QM_COMPLAINT.CID |
| CFILE_NAME | string | 是 | - | 文件名称 |
| CFILE_PATH | string | 是 | - | Minio文件存储路径 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_QM_COMPLAINT_IMAGE.CCOMPLAINT_ID = TBL_QM_COMPLAINT.CID

---

#### 81 检验记录主表 ( TBL_QM_INSPECT_RECORD )
- **业务含义**：包含IPQC首件检验记录的主体信息列表
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CCHECK_REMARK | string | 是 | - | 审核备注 |
| CCHECK_TIME | DateTime? | 是 | - | 审核时间 |
| CCHECK_USER_NAME | string | 是 | - | 审核人，对应TBL_SYS_USER.CUSER_NAME |
| CDECISION_MODE | int | 否 | - | 判定模式：1系统自动判定、2用户人为判定 |
| CINSPECT_CODE | string | 是 | - | 检验单号 |
| CINSPECT_QTY | decimal? | 是 | - | 检验数量 |
| CINSPECT_TIME | DateTime? | 是 | - | 检验时间 |
| CINSPECT_TYPE | int | 否 | - | 检验类型：1首件、2巡检 |
| CINSPECT_USER_NAME | string | 是 | - | 检验人，对应TBL_SYS_USER.CUSER_NAME |
| CIS_LAB | string | 是 | - | 是否送实验室 |
| CITEM_ID | long? | 是 | - | 外键，产品ID  对应TBL_BD_ITEM.CID |
| CLAB_INSPECT_REMARK | string | 是 | - | 实验室检验备注 |
| CLAB_INSPECT_TIME | DateTime? | 是 | - | 实验室检验时间 |
| CLAB_INSPECT_USER_NAME | string | 是 | - | 实验室检验人，对应TBL_SYS_USER.CUSER_NAME |
| CLAB_RECEIVE_TIME | DateTime? | 是 | - | 实验室接收时间 |
| CLAB_RECEIVE_USER_NAME | string | 是 | - | 实验室接收人，对应TBL_SYS_USER.CUSER_NAME |
| CMO_LOT | string | 是 | - | 工单批次 |
| CNG_DISPOSAL | string | 是 | - | 不良处置 |
| CPROCESS_ID | long | 否 | - | 工序ID，对应TBL_BD_PROCESS.CID |
| CREMARK | string | 是 | - | 备注 |
| CRESULT | int | 否 | - | 检验结果：1合格、2不合格 |
| CSCAN_BARCODE | string | 是 | - | 扫描条码 |
| CSHIFT | string | 是 | - | 班次 |
| CSTATUS | int | 否 | - | 状态：0待检验、1已检验待审核、2审核通过、3审核驳回 |
| CSUBMIT_QTY | decimal? | 是 | - | 报检数量 |
| CTEMPLATE_ID | long | 否 | - | 模板ID，对应TBL_NP_TEMPLATE.CID |
| CUNIT | string | 是 | - | 单位 |
| CUSTOMER_CODE | string | 是 | - | 客户编码，对应TBL_BD_CUSTOMER.CUSTOMER_NO |
| CID | long | 否 | - | 主键 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_QM_INSPECT_RECORD.CITEM_ID = TBL_BD_ITEM.CID
  - TBL_QM_INSPECT_RECORD.CPROCESS_ID = TBL_BD_PROCESS.CID
  - TBL_QM_INSPECT_RECORD.CTEMPLATE_ID = TBL_NP_TEMPLATE.CID
  - TBL_QM_INSPECT_RECORD.CUSTOMER_CODE = TBL_BD_CUSTOMER.CUSTOMER_NO
  - TBL_QM_INSPECT_RECORD.CCHECK_USER_NAME = TBL_SYS_USER.CUSER_NAME
  - TBL_QM_INSPECT_RECORD.CINSPECT_USER_NAME = TBL_SYS_USER.CUSER_NAME
  - TBL_QM_INSPECT_RECORD.CLAB_INSPECT_USER_NAME = TBL_SYS_USER.CUSER_NAME
  - TBL_QM_INSPECT_RECORD.CLAB_RECEIVE_USER_NAME = TBL_SYS_USER.CUSER_NAME
  - TBL_QM_INSPECT_RECORD.CID = TBL_QM_INSPECTION_RECORD_ITEM.CINSPECTION_RECORD_ID

---

#### 82 检验记录明细表 ( TBL_QM_INSPECTION_RECORD_ITEM )
- **业务含义**：包含IPQC首件检验记录的明细项目信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CALARM_MAX_VALUE | decimal? | 是 | - | 预警上限 |
| CALARM_MIN_VALUE | decimal? | 是 | - | 预警下限 |
| CIMG | string | 是 | - | 图片Base64编码 |
| CINPUT_VALUE | string | 是 | - | 输入值 |
| CINSEPCT_WAY | int | 否 | - | 检验方式 |
| CINSPECTION_RECORD_ID | long | 否 | - | 检验记录主表ID，对应TBL_QM_INSPECT_RECORD.CID |
| CIS_PHYSICS_LAB | string | 是 | - | 是否送物理实验室，Y：是；N：否 |
| CREMARK | string | 是 | - | 备注 |
| CRESULT | int | 否 | - | 检验结果：2不合格，1合格 |
| CSAMPLE_QTY | string | 是 | - | 抽样数量 |
| CSEQ | int? | 是 | - | 顺序号 |
| CSTANDARD_MAX_ALLOW | string | 是 | - | 标准上限是否允许等于，Y：是；N：否 |
| CSTANDARD_MAX_VALUE | decimal? | 是 | - | 标准上限 |
| CSTANDARD_MIN_ALLOW | string | 是 | - | 标准下限是否允许等于，Y：是；N：否 |
| CSTANDARD_MIN_VALUE | decimal? | 是 | - | 标准下限 |
| CSTANDARD_VALUE | string | 是 | - | 标准值 |
| CSTANDARD_VALUE_TYPE | int? | 是 | - | 标准值类型 |
| CTEMPLATE_ITEM_CODE | string | 是 | - | 模板项目编码 |
| CTEMPLATE_ITEM_DESC | string | 是 | - | 模板项目描述 |
| CTEMPLATE_ITEM_ID | long | 否 | - | 模板项目ID，对应TBL_NP_TEMPLATE_ITEM.CID |
| CTEMPLATE_ITEM_NAME | string | 是 | - | 模板项目名称 |
| CTEMPLATE_ITEM_TAG | string | 是 | - | 模板项目标签 |
| CUNIT | string | 是 | - | 单位 |
| LOWER_TOLERANCE | decimal? | 是 | - | 下公差 |
| orientation | string | 是 | - | 图片方向 |
| UPPER_TOLERANCE | decimal? | 是 | - | 上公差 |
| url | string | 是 | - | 图片地址 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_QM_INSPECTION_RECORD_ITEM.CINSPECTION_RECORD_ID = TBL_QM_INSPECT_RECORD.CID
  - TBL_QM_INSPECTION_RECORD_ITEM.CTEMPLATE_ITEM_ID = TBL_NP_TEMPLATE_ITEM.CID

---

#### 83 药缸信息表 ( TBL_QM_MEDICINE_TANK )
- **业务含义**：包含药水化验缸体的配置信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CMEDICINE_TANK_NAME | string | 是 | - | 药缸名称 |
| CMEDICINE_TANK_NO | string | 是 | - | 药缸编号 |
| CREMARK | string | 是 | - | 备注 |
| CWC_ID | long | 否 | - | 工作中心ID，对应TBL_BD_WC.CID |
| CID | long | 否 | - | 主键 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_QM_MEDICINE_TANK.CWC_ID = TBL_BD_WC.CID
  - TBL_QM_MEDICINE_TANK.CID = TBL_QM_ASSAY_LOG.CMEDICINE_TANK_ID

---

#### 84 物理实验室送检记录主表 ( TBL_QM_PL_LOG )
- **业务含义**：包含产品送检物理实验室的检验记录信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CCHECK_REMARK | string | 是 | - | 审核备注 |
| CCHECK_TIME | DateTime? | 是 | - | 审核时间 |
| CCHECK_USER | string | 是 | - | 审核人，对应TBL_SYS_USER.CUSER_NAME |
| CINSPECT_CODE | string | 是 | - | 检验单号 |
| CINSPECT_QTY | decimal? | 是 | - | 检验数量 |
| CINSPECT_REMARK | string | 是 | - | 检验备注 |
| CINSPECT_TIME | DateTime? | 是 | - | 检验时间 |
| CINSPECT_TYPE | int? | 是 | - | 检验类型 |
| CINSPECT_USER | string | 是 | - | 检验人，对应TBL_SYS_USER.CUSER_NAME |
| CIS_LAB | string | 是 | - | 是否送检（Y：IPQC送检，N：物理实验室自行提交） |
| CITEM_ID | long | 否 | - | 外键，产品ID  对应TBL_BD_ITEM.CID |
| CMO_LOT | string | 是 | - | 工单批次，对应TBL_MO.CMO_LOT |
| CNG_DISPOSAL | string | 是 | - | 不良处置 |
| CPOSITION | string | 是 | - | 送检位置 |
| CPROCESS_ID | long | 否 | - | 工序ID，对应TBL_BD_PROCESS.CID |
| CRECEIVE_TIME | DateTime? | 是 | - | 接收时间 |
| CRECEIVE_USER | string | 是 | - | 接收人，对应TBL_SYS_USER.CUSER_NAME |
| CREMARK | string | 是 | - | 备注 |
| CRESULT | int? | 是 | - | 结果；1：检验合格；0：检验不合格 |
| CSCAN_BARCODE | string | 是 | - | 扫描条码 |
| CSHIFT | string | 是 | - | 班次 |
| CSTATUS | int? | 是 | - | 状态，1：未检验；2：已检验 |
| CSUBMIT_QTY | decimal? | 是 | - | 报检数量 |
| CSUBMIT_REMARK | string | 是 | - | 送检备注 |
| CSUBMIT_REQUEST | string | 是 | - | 送检要求 |
| CSUBMIT_TIME | DateTime? | 是 | - | 送检时间 |
| CSUBMIT_USER | string | 是 | - | 送检人，对应TBL_SYS_USER.CUSER_NAME |
| CTEMPLATE_ID | long | 否 | - | 模板ID，对应TBL_NP_TEMPLATE.CID |
| CUNIT | string | 是 | - | 单位 |
| CUSTOMER_CODE | string | 是 | - | 客户编码，对应TBL_BD_CUSTOMER.CUSTOMER_NO |
| CWC_ID | long | 否 | - | 工作中心ID，对应TBL_BD_WC.CID |
| CID | long | 否 | - | 主键 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_QM_PL_LOG.CITEM_ID = TBL_BD_ITEM.CID
  - TBL_QM_PL_LOG.CPROCESS_ID = TBL_BD_PROCESS.CID
  - TBL_QM_PL_LOG.CTEMPLATE_ID = TBL_NP_TEMPLATE.CID
  - TBL_QM_PL_LOG.CWC_ID = TBL_BD_WC.CID
  - TBL_QM_PL_LOG.CUSTOMER_CODE = TBL_BD_CUSTOMER.CUSTOMER_NO
  - TBL_QM_PL_LOG.CMO_LOT = TBL_MO.CMO_LOT
  - TBL_QM_PL_LOG.CCHECK_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_QM_PL_LOG.CINSPECT_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_QM_PL_LOG.CRECEIVE_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_QM_PL_LOG.CSUBMIT_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_QM_PL_LOG.CID = TBL_QM_PL_LOG_ITEM.CPL_LOG_ID

---

#### 85 物理实验室送检记录明细表 ( TBL_QM_PL_LOG_ITEM )
- **业务含义**：包含产品送检物理实验室的检验记录的项目明细信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CALARM_MAX_VALUE | decimal? | 是 | - | 预警上限 |
| CALARM_MIN_VALUE | decimal? | 是 | - | 预警下限 |
| CINPUT_VALUE | string | 是 | - | 输入值 |
| CINPUT_VALUE_COUNT | int | 否 | - | 输入值数量，默认1 |
| CPL_LOG_ID | long | 否 | - | 送检主表ID，对应TBL_QM_PL_LOG.CID |
| CPOSITION | string | 是 | - | 位置 |
| CREMARK | string | 是 | - | 备注 |
| CRESULT | int? | 是 | - | 判定结果；1：检验合格；0：检验不合格 |
| CSCRAP_QTY | int | 否 | - | 报废数量 |
| CSEQ | int? | 是 | - | 顺序号 |
| CSTANDARD_MAX_ALLOW | string | 是 | - | 标准上限是否允许等于，Y：是；N：否 |
| CSTANDARD_MAX_VALUE | decimal? | 是 | - | 标准上限 |
| CSTANDARD_MIN_ALLOW | string | 是 | - | 标准下限是否允许等于，Y：是；N：否 |
| CSTANDARD_MIN_VALUE | decimal? | 是 | - | 标准下限 |
| CSTANDARD_VALUE | string | 是 | - | 标准值 |
| CSTANDARD_VALUE_TYPE | int? | 是 | - | 标准值类型 |
| CSUBMIT_REQUEST | string | 是 | - | 送检要求 |
| CTEMPLATE_ITEM_CODE | string | 是 | - | 模板项目编码 |
| CTEMPLATE_ITEM_DESC | string | 是 | - | 模板项目描述 |
| CTEMPLATE_ITEM_ID | long | 否 | - | 模板项目ID，对应TBL_NP_TEMPLATE_ITEM.CID |
| CTEMPLATE_ITEM_NAME | string | 是 | - | 模板项目名称 |
| CTEMPLATE_ITEM_TAG | string | 是 | - | 模板项目标签 |
| CTEXTBOX_QTY | int | 否 | - | 文本框数量 |
| CUNIT | string | 是 | - | 单位 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_QM_PL_LOG_ITEM.CPL_LOG_ID = TBL_QM_PL_LOG.CID
  - TBL_QM_PL_LOG_ITEM.CTEMPLATE_ITEM_ID = TBL_NP_TEMPLATE_ITEM.CID

---

### 2.6 文件管理

> 本章节数据来源于 Excel 工作表：`文件管理`

#### 86 联络单信息表 ( TBL_ESOP_CONTACT_FORM )
- **业务含义**：包含了MES系统中维护的内部联络单列表信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CAPPLICANT_NO | string | 是 | - | 申请编号 |
| CAPPROVAL_DATE | DateTime? | 是 | - | 批准日期 |
| CAPPROVAL_DESC | string | 是 | - | 批准意见 |
| CAPPROVAL_RESULT | int? | 是 | - | 批准结果：1同意、2驳回 |
| CAPPROVAL_USER | string | 是 | - | 批准人，对应TBL_SYS_USER.CUSER_NAME |
| CBACKGROUND | string | 是 | - | 背景 |
| CCATEGORY | string | 是 | - | 分类 |
| CCOUNTERSIGN | int? | 是 | - | 会签状态：1会签完成；0未会签通过 |
| CFILE_PATH | string | 是 | - | 附件 |
| CISSUE_DATE | DateTime? | 是 | - | 发出日期 |
| CISSUE_USER | string | 是 | - | 发出人，对应TBL_SYS_USER.CUSER_NAME |
| CPRESENTATION | string | 是 | - | 呈送 |
| CREVIEW_DATE | DateTime? | 是 | - | 审核日期 |
| CREVIEW_DESC | string | 是 | - | 审核意见 |
| CREVIEW_RESULT | int? | 是 | - | 审核结果：1同意、2驳回 |
| CREVIEW_USER | string | 是 | - | 审核人，对应TBL_SYS_USER.CUSER_NAME |
| CSHADOW_COPY | string | 是 | - | 影送 |
| CSUBJECT | string | 是 | - | 主题 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_ESOP_CONTACT_FORM.CAPPROVAL_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_ESOP_CONTACT_FORM.CISSUE_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_ESOP_CONTACT_FORM.CREVIEW_USER = TBL_SYS_USER.CUSER_NAME

---

#### 87 4M文件会签信息表 ( TBL_ESOP_COUNTERSIGN )
- **业务含义**：包含了MES系统中维护的4M变更单的会签信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CDATE | DateTime? | 是 | - | 会签日期 |
| CDEPT_NAME | string | 是 | - | 会签部门 |
| CMAIN_ID | long | 否 | - | 主表ID，对应TBL_ESOP_TEMPORARY_CHANGE_ORDER.CID |
| CREMARK | string | 是 | - | 会签备注 |
| CTYPE | int? | 是 | - | 类型（1:4M文件、2:联络单） |
| CUSER_NAME | string | 是 | - | 会签人，对应TBL_SYS_USER.CUSER_NAME |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_ESOP_COUNTERSIGN.CMAIN_ID = TBL_ESOP_TEMPORARY_CHANGE_ORDER.CID
  - TBL_ESOP_COUNTERSIGN.CUSER_NAME = TBL_SYS_USER.CUSER_NAME

---

#### 88 ESOP文件主表 ( TBL_ESOP_FILE )
- **业务含义**：包含了MES系统中维护的相关文件信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CAUDIT_MAN | string | 是 | - | 审核人，对应TBL_SYS_USER.CUSER_NAME |
| CAUDIT_TIME | DateTime? | 是 | - | 审核时间 |
| CCOMPANY | string | 是 | - | 测试公司 |
| CEXPIRY_DATE | DateTime? | 是 | - | 有效期 |
| CFILE_CATEGORY | long? | 是 | - | 文件目录ID，对应TBL_ESOP_FILE_CATEGORY.CID |
| CFILE_LEVEL | string | 是 | - | 文件等级 |
| CFILE_NAME | string | 是 | - | 文件名称 |
| CFILE_NO | string | 是 | - | 文件编号 |
| CFILE_PATH | string | 是 | - | 文件路径 |
| CFILE_TYPE | long | 否 | - | 文件类型ID，对应TBL_ESOP_FILE_TYPE.CID |
| CFILE_VERSION | string | 是 | - | 文件版本 |
| CIS_AUDIT | string | 是 | - | 是否审核，Y：是；N：否 |
| CMODEL | string | 是 | - | 型号 |
| CREMARK | string | 是 | - | 备注 |
| CREPORT_STATUS | int? | 是 | - | 测试报告状态：1：正常、2：临期（距到期时间30天内）、3：过期 |
| CREPORT_TYPE | string | 是 | - | 报告类型 |
| CSCRAP_REMARK | string | 是 | - | 报废备注 |
| CSCRAP_TIME | DateTime? | 是 | - | 报废时间 |
| CSCRAP_USER | string | 是 | - | 报废人，对应TBL_SYS_USER.CUSER_NAME |
| CSTATUS | int? | 是 | - | 状态（1：正常、2：报废） |
| CSUPPLIER | string | 是 | - | 供应商 |
| CTEMP_NAME | string | 是 | - | 模板名称 |
| CTEMP_NO | string | 是 | - | 模板编号 |
| CTEST_DATE | DateTime? | 是 | - | 测试日期 |
| CTYPE | string | 是 | - | 相关联的物料类型 |
| CURL | string | 是 | - | 文件访问地址 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_ESOP_FILE.CFILE_CATEGORY = TBL_ESOP_FILE_CATEGORY.CID
  - TBL_ESOP_FILE.CFILE_TYPE = TBL_ESOP_FILE_TYPE.CID
  - TBL_ESOP_FILE.CAUDIT_MAN = TBL_SYS_USER.CUSER_NAME
  - TBL_ESOP_FILE.CSCRAP_USER = TBL_SYS_USER.CUSER_NAME

---

#### 89 ESOP文件目录表 ( TBL_ESOP_FILE_CATEGORY )
- **业务含义**：描述了MES系统中维护的文件的目录信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CFILE_CATEGORY_NAME | string | 是 | - | 分类名称 |
| CFILE_CATEGORY_NO | string | 是 | - | 分类编号 |
| CFILE_CATEGORY_PATH | string | 是 | - | 分类层级路径 |
| CPARENT_ID | long | 否 | - | 上级目录ID，对应TBL_ESOP_FILE_CATEGORY.CID |
| CSEQ | int | 否 | - | 排序号 |
| CID | long | 否 | - | 主键 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_ESOP_FILE_CATEGORY.CPARENT_ID = TBL_ESOP_FILE_CATEGORY.CID
  - TBL_ESOP_FILE_CATEGORY.CID = TBL_ESOP_FILE.CFILE_CATEGORY

---

#### 90 文件手写体信息 ( TBL_ESOP_FILE_SIGN )
- **业务含义**：包含某些文件会签时需要用到的手写体信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CFILE_PATH | string | 是 | - | 签名文件路径 |
| CFILE_TYPE | string | 是 | - | 签名文件类型 |
| CUSER_NAME | string | 是 | - | 用户姓名 |
| CUSER_NO | string | 是 | - | 用户工号，对应TBL_SYS_USER.CUSER_NAME |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_ESOP_FILE_SIGN.CUSER_NO = TBL_SYS_USER.CUSER_NAME

---

#### 91 ESOP文件类型表 ( TBL_ESOP_FILE_TYPE )
- **业务含义**：定义了所有上传的文件可能对应的文件类型信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CFILE_EXTENDED | string | 是 | - | 允许的文件后缀 |
| CTYPE_DESC | string | 是 | - | 类型描述 |
| CTYPE_NAME | string | 是 | - | 类型名称 |
| CTYPE_NO | string | 是 | - | 类型编号 |
| CID | long | 否 | - | 主键 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_ESOP_FILE_TYPE.CID = TBL_ESOP_FILE.CFILE_TYPE

---

#### 92 4M临时变更单 ( TBL_ESOP_TEMPORARY_CHANGE_ORDER )
- **业务含义**：包含4M临时变更单的列表，在物料防错时需要校验订单号对应的变更情况
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CAFTER_ITEM | string | 是 | - | 变更后料号 |
| CAPPLICANT_DATE | DateTime? | 是 | - | 申请日期 |
| CAPPLICANT_DEPARTMENT | string | 是 | - | 申请部门 |
| CAPPLICANT_NAME | string | 是 | - | 申请人，对应TBL_SYS_USER.CUSER_NAME |
| CAPPLICANT_NO | string | 是 | - | 申请编号 |
| CAPPLY_SOP | bool? | 是 | - | 申请标准化 |
| CAPPLY_VERIFY | bool? | 是 | - | 申请重新验证 |
| CATTACHMENT_AFTER | string | 是 | - | 上传附件（变更后） |
| CATTACHMENT_BEFORE | string | 是 | - | 上传附件（变更前） |
| CBEFORE_ITEM | string | 是 | - | 变更前料号 |
| CCHANGE_AFTER | string | 是 | - | 变更后 |
| CCHANGE_BEFORE | string | 是 | - | 变更前 |
| CCHANGE_PERIOD | string | 是 | - | 变更期限 |
| CCONFIRM_DATE | DateTime? | 是 | - | 品质确认时间 |
| CCONFIRM_USER | string | 是 | - | 品质确认人，对应TBL_SYS_USER.CUSER_NAME |
| CCOUNTERSIGN | int? | 是 | - | 会签状态：1：会签完成；0：未会签 |
| CERP_FILE_NO | string | 是 | - | ERP文件 |
| CEXECUTION_DATE | DateTime? | 是 | - | 执行变更日期 |
| CEXPIRY_DATE | DateTime? | 是 | - | 有效期 |
| CINVOLVED_ITEM_NO | string | 是 | - | 涉及料号，对应TBL_BD_ITEM.CITEM_NO |
| CINVOLVED_MACHINE | bool? | 是 | - | 涉及机器 |
| CINVOLVED_MATERIAL | bool? | 是 | - | 涉及材料 |
| CINVOLVED_METHOD | bool? | 是 | - | 涉及方法 |
| CINVOLVED_PROCESS | string | 是 | - | 涉及变更工序，对应TBL_BD_PROCESS.CPROCESS_NAME |
| CINVOLVED_USER | bool? | 是 | - | 涉及人员 |
| CIS_RECOVERY | bool? | 是 | - | 恢复原状 |
| CNEW_4M_NAME | string | 是 | - | 新4M名称 |
| CORDER_NUMBER | string | 是 | - | 订单号 |
| CPREVIOUS_INVENTORY_HANDLING | string | 是 | - | 变更前在制品、库存品处理方式 |
| CREASON_AND_PURPOSE | string | 是 | - | 变更原因及目的 |
| CREVIEW_DATE | DateTime? | 是 | - | 审核时间 |
| CREVIEW_DESC | string | 是 | - | 审核意见 |
| CREVIEW_RESULT | int? | 是 | - | 审核结果：1：同意、2：不同意 |
| CREVIEW_TODO | bool | 否 | - | 是否生成代码事项 |
| CREVIEW_USER | string | 是 | - | 审核人，对应TBL_SYS_USER.CUSER_NAME |
| CID | long | 否 | - | 主键 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_ESOP_TEMPORARY_CHANGE_ORDER.CINVOLVED_ITEM_NO = TBL_BD_ITEM.CITEM_NO
  - TBL_ESOP_TEMPORARY_CHANGE_ORDER.CAPPLICANT_NAME = TBL_SYS_USER.CUSER_NAME
  - TBL_ESOP_TEMPORARY_CHANGE_ORDER.CCONFIRM_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_ESOP_TEMPORARY_CHANGE_ORDER.CREVIEW_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_ESOP_TEMPORARY_CHANGE_ORDER.CID = TBL_ESOP_COUNTERSIGN.CMAIN_ID
  - TBL_ESOP_TEMPORARY_CHANGE_ORDER.CID = TBL_FOURM_CHANGE_ITEM_LOG.CFOURM_ID
  - TBL_ESOP_TEMPORARY_CHANGE_ORDER.CINVOLVED_PROCESS = TBL_BD_PROCESS.CPROCESS_NAME

---

#### 93 4M变更料号日志表 ( TBL_FOURM_CHANGE_ITEM_LOG )
- **业务含义**：包含4M临时变更单的详细板料变更信息，即变更前板料和变更后板料
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CAFTER_ITEM | string | 是 | - | 变更后板材料号，对应TBL_BD_ITEM.CITEM_NO |
| CBEFOR_ITEM | string | 是 | - | 变更前板材料号，对应TBL_BD_ITEM.CITEM_NO |
| CFOURM_ID | long | 否 | - | 表单ID，对应TBL_ESOP_TEMPORARY_CHANGE_ORDER.CID |
| CPART | string | 是 | - | 部件 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_FOURM_CHANGE_ITEM_LOG.CFOURM_ID = TBL_ESOP_TEMPORARY_CHANGE_ORDER.CID
  - TBL_FOURM_CHANGE_ITEM_LOG.CAFTER_ITEM = TBL_BD_ITEM.CITEM_NO
  - TBL_FOURM_CHANGE_ITEM_LOG.CBEFOR_ITEM = TBL_BD_ITEM.CITEM_NO

---

### 2.7 点检保养

> 本章节数据来源于 Excel 工作表：`点检保养`

#### 94 模板关联工作中心 ( TBL_EAM_PM_TEMP_WC_LINK )
- **业务含义**：描述了设备点检或设备保养模板与工作中心的关联关系
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CTEMP_ID | long? | 是 | - | 模板ID，对应TBL_NP_TEMPLATE.CID |
| CWC_ID | long? | 是 | - | 工作中心ID，对应TBL_BD_WC.CID |
| CID | long | 否 | - | 主键 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAM_PM_TEMP_WC_LINK.CTEMP_ID = TBL_NP_TEMPLATE.CID
  - TBL_EAM_PM_TEMP_WC_LINK.CWC_ID = TBL_BD_WC.CID
  - TBL_EAM_PM_TEMP_WC_LINK.CID = TBL_PM_TEMPLATE_LINK_DEVICE.CPM_TEMPLATE_WC_LINK_ID

---

#### 95 模板主表 ( TBL_NP_TEMPLATE )
- **业务含义**：包含所有的设备点检和设备保养模板信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CTEMPLATE_CODE | string | 是 | - | 模板编码 |
| CTEMPLATE_NAME | string | 是 | - | 模板名称 |
| CTEMPLATE_TYPE_ID | long? | 是 | - | 模板类型标识， TBL_NP_TEMPLATE_TYPE.CID |
| CID | long | 否 | - | 主键 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_NP_TEMPLATE.CID = TBL_EAM_PM_TEMP_WC_LINK.CTEMP_ID
  - TBL_NP_TEMPLATE.CID = TBL_NP_TEMPLATE_ITEM.CTEMPLATE_ID
  - TBL_NP_TEMPLATE.CID = TBL_EAM_MAINTAIN_TASK.CTEMP_ID
  - TBL_NP_TEMPLATE.CID = TBL_QM_INSPECT_RECORD.CTEMPLATE_ID
  - TBL_NP_TEMPLATE.CID = TBL_QM_PL_LOG.CTEMPLATE_ID

---

#### 96 模板变更主表 ( TBL_NP_TEMPLATE_CHANGE )
- **业务含义**：描述设备点检模板或设备保养模板的变更情况
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CAPPROVAL_ID | long? | 是 | - | 审批流标识 |
| CAUDIT_REMARK | string | 是 | - | 审核备注 |
| CAUDIT_STATUS | int | 否 | - | 审核状态 |
| CAUDIT_TIME | DateTime? | 是 | - | 审核时间 |
| CAUDIT_USER_ID | string | 是 | - | 审核人标识，对应TBL_SYS_USER.CUSER_NAME |
| CCHANGE_REMARK | string | 是 | - | 变更备注 |
| CCHANGE_TIME | DateTime | 否 | - | 变更时间 |
| CCHANGE_USER_ID | string | 是 | - | 变更人标识，对应TBL_SYS_USER.CUSER_NAME |
| CGROUP_ID | long | 否 | - | 分组标识 |
| CIS_NEW | string | 是 | - | 是否新增，Y：是；N：否 |
| CTEMPLATE_CODE | string | 是 | - | 模板编码，对应TBL_NP_TEMPLATE.CTEMPLATE_CTEMPLATE_CODE |
| CTEMPLATE_DESC | string | 是 | - | 模板描述 |
| CTEMPLATE_NAME | string | 是 | - | 模板名称 |
| CTEMPLATE_TYPE_ID | long | 否 | - | 模板类型标识， TBL_NP_TEMPLATE_TYPE.CID |
| CTEMPLATE_VERSION | double | 否 | - | 模板版本 |
| CID | long | 否 | - | 主键 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_NP_TEMPLATE_CHANGE.CTEMPLATE_TYPE_ID = TBL_NP_TEMPLATE_TYPE.CID
  - TBL_NP_TEMPLATE_CHANGE.CAUDIT_USER_ID = TBL_SYS_USER.CUSER_NAME
  - TBL_NP_TEMPLATE_CHANGE.CCHANGE_USER_ID = TBL_SYS_USER.CUSER_NAME
  - TBL_NP_TEMPLATE_CHANGE.CID = TBL_NP_TEMPLATE_CHANGE_ITEM.CTEMPLATE_CHANGE_ID
  - TBL_NP_TEMPLATE_CHANGE.CTEMPLATE_CODE = TBL_NP_TEMPLATE.CTEMPLATE_CTEMPLATE_CODE

---

#### 97 模板变更明细表 ( TBL_NP_TEMPLATE_CHANGE_ITEM )
- **业务含义**：描述设备点检模板或设备保养模板的项目明细的变更情况
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CALARM_MAX_VALUE | decimal? | 是 | - | 报警最大值（原值） |
| CALARM_MAX_VALUE_EDIT | decimal? | 是 | - | 报警最大值（变更后） |
| CALARM_MIN_VALUE | decimal? | 是 | - | 报警最小值（原值） |
| CALARM_MIN_VALUE_EDIT | decimal? | 是 | - | 报警最小值（变更后） |
| CCHECK_CONTENT | long | 否 | - | 检测内容标识（原值） |
| CCHECK_CONTENT_EDIT | long | 否 | - | 检测内容标识（变更后） |
| CCHECK_WAY | int | 否 | - | 检测方式（原值） |
| CCHECK_WAY_EDIT | int | 否 | - | 检测方式（变更后） |
| CDEFAULT_VALUE | string | 是 | - | 默认值（原值） |
| CDEFAULT_VALUE_EDIT | string | 是 | - | 默认值（变更后） |
| CDEFAULT_VALUE_TYPE | int | 否 | - | 默认值类型（原值） |
| CDEFAULT_VALUE_TYPE_EDIT | int | 否 | - | 默认值类型（变更后） |
| CDEVIATION_TYPE | int | 否 | - | 偏差类型（原值） |
| CDEVIATION_TYPE_EDIT | int | 否 | - | 偏差类型（变更后） |
| CFORMULA | string | 是 | - | 公式（原值） |
| CFORMULA_EDIT | string | 是 | - | 公式（变更后） |
| CINPUT_FORMULA | string | 是 | - | 输入公式（原值） |
| CINPUT_FORMULA_EDIT | string | 是 | - | 输入公式（变更后） |
| CINPUT_TYPE | int | 否 | - | 输入类型（原值） |
| CINPUT_TYPE_EDIT | int | 否 | - | 输入类型（变更后） |
| CIS_CHECK_RESULT | string | 是 | - | 是否参与结果判定（原值） |
| CIS_CHECK_RESULT_EDIT | string | 是 | - | 是否参与结果判定（变更后） |
| CIS_CHEMISTAY_LAB | string | 是 | - | 是否送化学实验室（原值） |
| CIS_CHEMISTAY_LAB_EDIT | string | 是 | - | 是否送化学实验室（变更后） |
| CIS_KEY_ITEM | string | 是 | - | 是否关键项（原值） |
| CIS_KEY_ITEM_EDIT | string | 是 | - | 是否关键项（变更后） |
| CIS_MUST | string | 是 | - | 是否必填（原值） |
| CIS_MUST_EDIT | string | 是 | - | 是否必填（变更后） |
| CIS_PHYSICS_LAB | string | 是 | - | 是否送物理实验室（原值） |
| CIS_PHYSICS_LAB_EDIT | string | 是 | - | 是否送物理实验室（变更后） |
| CIS_SHOW_STANDARD | string | 是 | - | 是否显示标准值（原值） |
| CIS_SHOW_STANDARD_EDIT | string | 是 | - | 是否显示标准值（变更后） |
| CITEM_FREQ_PERIOD_ID | long | 否 | - | 频次周期标识（原值） |
| CITEM_FREQ_PERIOD_ID_EDIT | long | 否 | - | 频次周期标识（变更后） |
| CLIST_SOURCE | string | 是 | - | 列表来源（原值） |
| CLIST_SOURCE_EDIT | string | 是 | - | 列表来源（变更后） |
| CLIST_SOURCE_TYPE | int | 否 | - | 列表来源类型（原值） |
| CLIST_SOURCE_TYPE_EDIT | int | 否 | - | 列表来源类型（变更后） |
| CSEQ | int | 否 | - | 排序序号（原值） |
| CSEQ_EDIT | int | 否 | - | 排序序号（变更后） |
| CSTANDARD_MAX_ALLOW | string | 是 | - | 标准最大允许值（原值） |
| CSTANDARD_MAX_ALLOW_EDIT | string | 是 | - | 标准最大允许值（变更后） |
| CSTANDARD_MAX_VALUE | decimal? | 是 | - | 标准最大值（原值） |
| CSTANDARD_MAX_VALUE_EDIT | decimal? | 是 | - | 标准最大值（变更后） |
| CSTANDARD_MIN_ALLOW | string | 是 | - | 标准最小允许值（原值） |
| CSTANDARD_MIN_ALLOW_EDIT | string | 是 | - | 标准最小允许值（变更后） |
| CSTANDARD_MIN_VALUE | decimal? | 是 | - | 标准最小值（原值） |
| CSTANDARD_MIN_VALUE_EDIT | decimal? | 是 | - | 标准最小值（变更后） |
| CSTANDARD_VALUE | string | 是 | - | 标准值（原值） |
| CSTANDARD_VALUE_EDIT | string | 是 | - | 标准值（变更后） |
| CSTANDARD_VALUE_TYPE | int | 否 | - | 标准值类型（原值） |
| CSTANDARD_VALUE_TYPE_EDIT | int | 否 | - | 标准值类型（变更后） |
| CSUM_FIELD | string | 是 | - | 求和字段（原值） |
| CSUM_FIELD_EDIT | string | 是 | - | 求和字段（变更后） |
| CTEMPLATE_CHANGE_ID | long | 否 | - | 变更ID， 对应TBL_NP_TEMPLATE_CHANGE.CID |
| CTEMPLATE_ITEM_CODE | string | 是 | - | 模板项编码 |
| CTEMPLATE_ITEM_DESC | string | 是 | - | 模板项描述（原值） |
| CTEMPLATE_ITEM_DESC_EDIT | string | 是 | - | 模板项描述（变更后） |
| CTEMPLATE_ITEM_NAME | string | 是 | - | 模板项名称（原值） |
| CTEMPLATE_ITEM_NAME_EDIT | string | 是 | - | 模板项名称（变更后） |
| CTEMPLATE_ITEM_TAG | string | 是 | - | 模板项标签（原值） |
| CTEMPLATE_ITEM_TAG_EDIT | string | 是 | - | 模板项标签（变更后） |
| CTOOL_ID | long | 否 | - | 工具标识（原值） |
| CTOOL_ID_EDIT | long | 否 | - | 工具标识（变更后） |
| CUNIT | string | 是 | - | 单位（原值） |
| CUNIT_EDIT | string | 是 | - | 单位（变更后） |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_NP_TEMPLATE_CHANGE_ITEM.CTEMPLATE_CHANGE_ID = TBL_NP_TEMPLATE_CHANGE.CID

---

#### 98 模板项配置表 ( TBL_NP_TEMPLATE_ITEM )
- **业务含义**：包含所有的设备点检和设备保养模板的详细项目信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CALARM_MAX_VALUE | decimal | 否 | - | 报警最大值 |
| CALARM_MIN_VALUE | decimal | 否 | - | 报警最小值 |
| CCHECK_CONTENT | long | 否 | - | 检测内容标识 |
| CCHECK_WAY | int | 否 | - | 检测方式 |
| CDEFAULT_VALUE | string | 是 | - | 默认值 |
| CDEFAULT_VALUE_TYPE | int | 否 | - | 默认值类型 |
| CDEVIATION_TYPE | int | 否 | - | 偏差类型 |
| CINPUT_TYPE | int | 否 | - | 输入类型 |
| CIS_CHECK_RESULT | string | 是 | - | 是否参与结果判定 |
| CIS_CHEMISTAY_LAB | string | 是 | - | 是否送化学实验室 |
| CIS_KEY_ITEM | string | 是 | - | 是否关键项 |
| CIS_MUST | string | 是 | - | 是否必填 |
| CIS_PHYSICS_LAB | string | 是 | - | 是否送物理实验室 |
| CIS_SHOW_STANDARD | string | 是 | - | 是否显示标准值 |
| CITEM_FREQ_PERIOD_ID | long | 否 | - | 项目频次周期标识 |
| CLIST_SOURCE | string | 是 | - | 列表来源 |
| CLIST_SOURCE_TYPE | int | 否 | - | 列表来源类型 |
| CSEQ | int | 否 | - | 排序序号 |
| CSTANDARD_MAX_ALLOW | string | 是 | - | 标准最大允许值 |
| CSTANDARD_MAX_VALUE | decimal? | 是 | - | 标准最大值 |
| CSTANDARD_MIN_ALLOW | string | 是 | - | 标准最小允许值 |
| CSTANDARD_MIN_VALUE | decimal? | 是 | - | 标准最小值 |
| CSTANDARD_VALUE | string | 是 | - | 标准值 |
| CSTANDARD_VALUE_TYPE | int | 否 | - | 标准值类型 |
| CSTANDRAD_SOURCE | string | 是 | - | 标准来源 |
| CSUM_FIELD | string | 是 | - | 求和字段 |
| CTEMPLATE_ID | long | 否 | - | 模板ID， 对应TBL_NP_TEMPLATE.CID |
| CTEMPLATE_ITEM_CODE | string | 是 | - | 模板项编码 |
| CTEMPLATE_ITEM_DESC | string | 是 | - | 模板项描述 |
| CTEMPLATE_ITEM_NAME | string | 是 | - | 模板项名称 |
| CTEMPLATE_ITEM_TAG | string | 是 | - | 模板项标签 |
| CTOOL_ID | long | 否 | - | 工具标识 |
| CUNIT | string | 是 | - | 单位 |
| LOWER_TOLERANCE | decimal? | 是 | - | 下公差 |
| UPPER_TOLERANCE | decimal? | 是 | - | 上公差 |
| CID | long | 否 | - | 主键 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_NP_TEMPLATE_ITEM.CTEMPLATE_ID = TBL_NP_TEMPLATE.CID
  - TBL_NP_TEMPLATE_ITEM.CID = TBL_QM_INSPECTION_RECORD_ITEM.CTEMPLATE_ITEM_ID
  - TBL_NP_TEMPLATE_ITEM.CID = TBL_QM_PL_LOG_ITEM.CTEMPLATE_ITEM_ID
  - TBL_NP_TEMPLATE_ITEM.CID = TBL_EAM_MAINTAIN_TASK_ITEM.CITEM_ID
  - TBL_NP_TEMPLATE_ITEM.CID = TBL_EAP_POTION_ITEM_CONTROL_LINK.CNP_ITEM_ID

---

#### 99 设备故障代码表 ( TBL_EAM_ERROR_CODE )
- **业务含义**：描述了设备的各种故障情况的代码以及说明
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CERROR_CODE | string | 是 | - | 故障代码 |
| CERROR_DESC | string | 是 | - | 故障描述 |
| CERROR_LEVEL | string | 是 | - | 故障等级 |
| CERROR_NAME | string | 是 | - | 故障名称 |
| CERROR_TYPE | string | 是 | - | 故障类型 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAM_ERROR_CODE.CID = TBL_EAM_REPAIR.CERROR_ID

---

#### 100 设备保养频次配置表 ( TBL_EAM_FREQUENCY )
- **业务含义**：描述了设备点检或设备保养的任务频率常量信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CCOUNT | int | 否 | - | 频次数值 |
| CCOUNT_UNIT | string | 是 | - | 计数单位 |
| CFREQ_DESC | string | 是 | - | 频次说明 |
| CFREQ_NAME | string | 是 | - | 频次名称 |
| CFREQ_UNIT | string | 是 | - | 频次单位 |
| CID | long | 否 | - | 主键 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：无

---

#### 101 保养任务主表 ( TBL_EAM_MAINTAIN_TASK )
- **业务含义**：包含了由定时程序定时生成的设备保养任务
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CAPPROVAL_ID | Int64 | 否 | - | 审批流ID |
| CAPPROVAL_STATUS | Int32 | 否 | - | 审批状态 |
| CBASE_TASK_NO | String | 是 | - | 基准任务编号 |
| CCHECK_REMARK | string | 是 | - | 点检备注 |
| CCHECK_STATUS | int | 否 | - | 点检状态 |
| CEMPOLYEE_NAME | String | 是 | - | 执行人姓名 |
| CEMPOLYEE_NO | String | 是 | - | 执行人工号，对应TBL_SYS_USER.CUSER_NAME |
| CIS_INTERVAL | bool | 否 | - | 是否按间隔生成任务 |
| CMAINTAIN_TIME | DateTime? | 是 | - | 保养执行时间 |
| CREMARK | string | 是 | - | 备注 |
| CRESULT | String | 是 | - | 保养结果，OK：合格；NG：不合格 |
| CTASK_CREATED_TIME | DateTime? | 是 | - | 任务创建时间 |
| CTASK_NO | String | 是 | - | 任务编码 |
| CTASK_STAND_TIME_E | DateTime? | 是 | - | 标准结束时间 |
| CTASK_STAND_TIME_S | DateTime? | 是 | - | 标准开始时间 |
| CTASK_STATUS | Int32 | 否 | - | 任务状态（0待执行,1已执行,2已关闭(未执行)） |
| CTASK_TAG | String | 是 | - | 任务标签（用于区分任务属于哪一个频次的第几次任务） |
| CTASK_TYPE | String | 是 | - | 任务类型（自动任务、手动任务、主动任务） |
| CTEMP_ID | Int64 | 否 | - | 模板ID，对应TBL_NP_TEMPLATE.CID |
| CTEMP_NAME | String | 是 | - | 模板名称 |
| CTEMP_NO | String | 是 | - | 模板编号 |
| CWC_ID | Int64 | 否 | - | 工作中心ID，对应TBL_BD_WC.CID |
| CID | long | 否 | - | 主键 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAM_MAINTAIN_TASK.CTEMP_ID = TBL_NP_TEMPLATE.CID
  - TBL_EAM_MAINTAIN_TASK.CWC_ID = TBL_BD_WC.CID
  - TBL_EAM_MAINTAIN_TASK.CEMPOLYEE_NO = TBL_SYS_USER.CUSER_NAME
  - TBL_EAM_MAINTAIN_TASK.CID = TBL_EAM_MAINTAIN_TASK_ITEM.CHID
  - TBL_EAM_MAINTAIN_TASK.CID = TBL_EAM_MAINTAIN_TASK_CHANGE_LOG.CTASK_ID

---

#### 102 保养任务时间变更日志表 ( TBL_EAM_MAINTAIN_TASK_CHANGE_LOG )
- **业务含义**：包含了更改保养任务时间的操作日志
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CNEW_TIME | string | 是 | - | 新计划时间 |
| COLD_TIME | string | 是 | - | 原计划时间 |
| CREMARK | string | 是 | - | 备注 |
| CTASK_ID | long | 否 | - | 任务ID，TBL_EAM_MAINTAIN_TASK.CID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAM_MAINTAIN_TASK_CHANGE_LOG.CTASK_ID = TBL_EAM_MAINTAIN_TASK.CID

---

#### 103 保养任务明细表 ( TBL_EAM_MAINTAIN_TASK_ITEM )
- **业务含义**：包含了由定时程序定时生成的设备保养任务的项目明细
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CALARM_MAX | Decimal | 否 | - | 报警上限 |
| CALARM_MIN | Decimal | 否 | - | 报警下限 |
| CDEFAULT_VALUE | String | 是 | - | 默认值 |
| CHID | Int64 | 否 | - | 任务主表ID，对应TBL_EAM_MAINTAIN_TASK.CID |
| CINPUT_TYPE | String | 是 | - | 输入类型 |
| CINPUT_VALUE | String | 是 | - | 输入值 |
| CIS_CHECK_RESULT | Boolean | 否 | - | 是否校验结果，1：是；0：否 |
| CIS_INTERVAL | Boolean | 否 | - | 是否按间隔生成任务，1：是；0：否 |
| CIS_KEY_ITEM | Boolean | 否 | - | 是否关键项，1：是；0：否 |
| CIS_MUST | Boolean | 否 | - | 是否必填，1：是；0：否 |
| CIS_MUST_UPLOAD_IMG | bool | 否 | - | 是否必须上传图片，1：是；0：否 |
| CIS_REGULAR | Boolean | 否 | - | 是否正则校验，1：是；0：否 |
| CIS_SERVICE_CHECK | Boolean | 否 | - | 是否服务校验，1：是；0：否 |
| CIS_SHOW_STANDARD | bool | 否 | - | 是否显示标准值，1：是；0：否 |
| CIS_SHOW_UPLOAD_IMG | bool | 否 | - | 是否显示上传图片入口，1：是；0：否 |
| CITEM_DESC | String | 是 | - | 项目描述 |
| CITEM_FREQ | String | 是 | - | 项目频次 |
| CITEM_ID | Int64 | 否 | - | 模板项ID，对应TBL_NP_TEMPLATE_ITEM.CID |
| CITEM_NAME | String | 是 | - | 项目名称 |
| CITEM_NO | String | 是 | - | 项目编号 |
| CITEM_TAG | String | 是 | - | 项目标记 |
| CLIST_SOURCE | String | 是 | - | 下拉数据源 |
| CREGULAR | String | 是 | - | 正则表达式 |
| CREGULAR_TIPS | String | 是 | - | 正则提示 |
| CREMARK | string | 是 | - | 备注 |
| CRESULT | string | 是 | - | 检查结果 |
| CSEQ | int | 否 | - | 排序 |
| CSERVICE | String | 是 | - | 服务地址 |
| CSTANDARD_VALUE | String | 是 | - | 标准值 |
| CTEMP_ID | Int64 | 否 | - | 模板ID，对应TBL_NP_TEMPLATE.CID |
| CUNIT | String | 是 | - | 单位 |
| CWARM_MAX | Decimal | 否 | - | 预警上限 |
| CWARM_MIN | Decimal | 否 | - | 预警下限 |
| CID | long | 否 | - | 主键 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAM_MAINTAIN_TASK_ITEM.CHID = TBL_EAM_MAINTAIN_TASK.CID
  - TBL_EAM_MAINTAIN_TASK_ITEM.CTEMP_ID = TBL_NP_TEMPLATE.CID
  - TBL_EAM_MAINTAIN_TASK_ITEM.CITEM_ID = TBL_NP_TEMPLATE_ITEM.CID
  - TBL_EAM_MAINTAIN_TASK_ITEM.CID = TBL_EAM_MAINTAIN_TASK_ITEM_IMG.CITEM_ID

---

#### 104 保养任务明细图片表 ( TBL_EAM_MAINTAIN_TASK_ITEM_IMG )
- **业务含义**：包含了提交设备保养结果时附带的图片信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CIMAGE_PATH | string | 是 | - | 图片路径 |
| CITEM_ID | Int64 | 否 | - | 保养任务明细ID，对应TBL_EAM_MAINTAIN_TASK_ITEM.CID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAM_MAINTAIN_TASK_ITEM_IMG.CITEM_ID = TBL_EAM_MAINTAIN_TASK_ITEM.CID

---

#### 105 维修工单主表 ( TBL_EAM_REPAIR )
- **业务含义**：包含了设备维修的记录信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CAPPLY_DATE | DateTime? | 是 | - | 报修时间 |
| CAPPLY_MAN | string | 是 | - | 报修人工号，对应TBL_SYS_USER.CUSER_NAME |
| CASSIGNMENT_DATE | DateTime? | 是 | - | 指派时间 |
| CASSIGNMENT_MAN | string | 是 | - | 指派人工号，对应TBL_SYS_USER.CUSER_NAME |
| CAUDIT_DEPARTMNT | string | 是 | - | 审核部门 |
| CAUDIT_STATUS | string | 是 | - | 审核状态 |
| CAUDIT_USERNAME | string | 是 | - | 审核/驳回人，对应TBL_SYS_USER.CUSER_NAME |
| CCAUSE | string | 是 | - | 故障根因 |
| CCLOSE_DATE | DateTime? | 是 | - | 关闭时间 |
| CCLOSE_MAN | string | 是 | - | 关闭人工号，对应TBL_SYS_USER.CUSER_NAME |
| CDEMAND_DATE | DateTime? | 是 | - | 要求完成时间 |
| CEND_REPAIR_DATE | DateTime? | 是 | - | 结束维修时间 |
| CERROR_DESC | string | 是 | - | 故障描述 |
| CERROR_ID | Int64 | 否 | - | 故障代码ID |
| CERROR_REASON | string | 是 | - | 故障原因描述 |
| CIS_PRODUCT | string | 是 | - | 是否停产（Y：是；N；否） |
| CIS_URGENT | string | 是 | - | 是否紧急（Y：是；N；否） |
| CODE | string | 是 | - | 用户工号，对应TBL_SYS_USER.CUSER_NAME |
| CPLAN_COMPLETE_DATE | DateTime? | 是 | - | 计划完成时间 |
| CREMARK | string | 是 | - | 备注 |
| CREPAIR_CODE | string | 是 | - | 维修单编号 |
| CREPAIR_DESC | string | 是 | - | 维修措施说明 |
| CREPAIR_MAN | string | 是 | - | 维修人工号，对应TBL_SYS_USER.CUSER_NAME |
| CSCORE | int | 否 | - | 评分 |
| CSTART_REPAIR_DATE | DateTime? | 是 | - | 开始维修时间 |
| CSTATUS | string | 是 | - | 工单状态；EAM_REPAIR_STATUS_ASSIGNMENT：维修指派；EAM_REPAIR_STATUS_COMPLETE：维修完成；EAM_REPAIR_STATUS_CLOSE：维修取消 |
| CWAIT_MATERIAL_DATE | DateTime? | 是 | - | 开始待料时间 |
| CWC_CHILDREN | long? | 是 | - | 设备故障子节点(设备ID) |
| CWC_ID | Int64 | 否 | - | 工作中心ID，对应TBL_BD_WC.CID |
| CID | long | 否 | - | 主键 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAM_REPAIR.CERROR_ID = TBL_EAM_ERROR_CODE.CID
  - TBL_EAM_REPAIR.CWC_ID = TBL_BD_WC.CID
  - TBL_EAM_REPAIR.CAPPLY_MAN = TBL_SYS_USER.CUSER_NAME
  - TBL_EAM_REPAIR.CASSIGNMENT_MAN = TBL_SYS_USER.CUSER_NAME
  - TBL_EAM_REPAIR.CAUDIT_USERNAME = TBL_SYS_USER.CUSER_NAME
  - TBL_EAM_REPAIR.CCLOSE_MAN = TBL_SYS_USER.CUSER_NAME
  - TBL_EAM_REPAIR.CODE = TBL_SYS_USER.CUSER_NAME
  - TBL_EAM_REPAIR.CREPAIR_MAN = TBL_SYS_USER.CUSER_NAME
  - TBL_EAM_REPAIR.CID = TBL_EAM_REPAIR_IMG.CREPAIR_ID
  - TBL_EAM_REPAIR.CID = TBL_EAM_REPAIR_MAN.CREPAIR_ID
  - TBL_EAM_REPAIR.CID = TBL_EAM_REPAIR_MATERIAL.CREPAIR_ID

---

#### 106 维修图片记录表 ( TBL_EAM_REPAIR_IMG )
- **业务含义**：包含了提交设备维修结果时附带的图片信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CIMAGE_PATH | string | 是 | - | 图片路径 |
| CREPAIR_ID | Int64 | 否 | - | 维修单ID，对应TBL_EAM_REPAIR.CID |
| CTYPE | int | 否 | - | 图片类型（1故障图片，2维修图片） |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAM_REPAIR_IMG.CREPAIR_ID = TBL_EAM_REPAIR.CID

---

#### 107 指派人员列表 ( TBL_EAM_REPAIR_MAN )
- **业务含义**：描述了维修可指派的人员的列表信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CREPAIR_CODE | string | 是 | - | 维修单编号 |
| CREPAIR_ID | long | 否 | - | 维修单ID，对应TBL_EAM_REPAIR.CID |
| CREPAIR_MAN_CODE_PRE | string | 是 | - | 指派人账号，对应TBL_SYS_USER.CUSER_NAME |
| CREPAIR_MAN_NAME_PRE | string | 是 | - | 指派人名称 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAM_REPAIR_MAN.CREPAIR_ID = TBL_EAM_REPAIR.CID
  - TBL_EAM_REPAIR_MAN.CREPAIR_MAN_CODE_PRE = TBL_SYS_USER.CUSER_NAME

---

#### 108 维修耗材记录表 ( TBL_EAM_REPAIR_MATERIAL )
- **业务含义**：包含提交设备维修结果时报告的耗材信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CMATERIAL_NAME | string | 是 | - | 物料名称 |
| CMATERIAL_SPEC | string | 是 | - | 物料规格 |
| CQTY | int | 否 | - | 数量 |
| CREPAIR_ID | Int64 | 否 | - | 维修单ID，对应TBL_EAM_REPAIR.CID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAM_REPAIR_MATERIAL.CREPAIR_ID = TBL_EAM_REPAIR.CID

---

### 2.8 生产流程

> 本章节数据来源于 Excel 工作表：`生产流程`

#### 109 叠板防错用户 ( TBL_SFC_DBFC_USER )
- **业务含义**：维护系统用户和指定设备的绑定关系
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CDEVICE_NO | string | 是 | - | 设备编码， 值为RR01、RR02、RR03 |
| CUSER_NAME | string | 是 | - | 用户账号，对应TBL_SYS_USER.CUSER_NAME |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_SFC_DBFC_USER.CUSER_NAME = TBL_SYS_USER.CUSER_NAME

---

#### 110 包装信息表 ( TBL_SFC_PACKAGE )
- **业务含义**：包含包装工序中所有的内包和外包信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CBARCODE | string | 是 | - | 包装条码 |
| CBATCH_NUMBER | string | 是 | - | 包装批次号 |
| CCUSTOMER_CODE | string | 是 | - | 客户编码，对应TBL_BD_CUSTOMER.CUSTOMER_NO |
| CCUSTOMER_ITEM_NAME | string | 是 | - | 客户品名 |
| CCUSTOMER_ITEM_NO | string | 是 | - | 客户料号 |
| CCYCLE | string | 是 | - | 周期 |
| CINVENTORY_STATUS | int? | 是 | - | 库存状态，0待提交、1待入库、2已入库、3已出库 |
| CIS_REPRINT | string | 是 | - | 是否补打，0非补打、1补打 |
| CITEM_ID | long? | 是 | - | 外键，产品或物料ID  对应 TBL_BD_ITEM.CID |
| CLEVEL | int? | 是 | - | 包装层级，1内包、2外包 |
| CLOCATION_ID | long? | 是 | - | 货位ID，对应TBL_WMS_LOCATION.CID |
| CMO_LOT | string | 是 | - | 工单号，对应TBL_MO.CMO_LOT |
| CNET_WEIGHT | decimal? | 是 | - | 净重 |
| CPACKING_TIME | DateTime? | 是 | - | 包装时间 |
| CPARAM_VALUE | string | 是 | - | 参数值（板厚） |
| CPARENT_ID | long? | 是 | - | 父级包装ID，对应TBL_SFC_PACKAGE.CID |
| CQTY | decimal? | 是 | - | 数量 |
| CREMARK | string | 是 | - | 备注 |
| CSALES_ORDER | string | 是 | - | 销售订单 |
| CSET_PCS_QTY | int? | 是 | - | SET开板数 |
| CSET_X_QTY | int? | 是 | - | SET叉板数 |
| CSOURCE_BARCODE | string | 是 | - | 补打前的箱号 |
| CSPLIT_DATETIME | DateTime? | 是 | - | 拆分时间 |
| CSPLIT_ID | long? | 是 | - | 拆分前的上级条码ID，对应TBL_SFC_PACKAGE.CID |
| CSTATUS | string | 是 | - | 状态，来源数据字典TBL_SYS_DICTIONARY.CDIC_CODE |
| CWEIGHT | decimal? | 是 | - | 毛重 |
| CX_QTY | string | 是 | - | 叉板数 |
| EXPAND1 | string | 是 | - | 扩展字段1（内箱3045流水号） |
| ScrapDateTime | string | 是 | - | 报废时间 |
| ScrapUser | string | 是 | - | 报废人，对应TBL_SYS_UER.CUSER_NAME |
| XOUT | string | 是 | - | 叉板数 |
| CID | long | 否 | - | 主键ID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_SFC_PACKAGE.CITEM_ID = TBL_BD_ITEM.CID
  - TBL_SFC_PACKAGE.CMO_LOT = TBL_MO.CMO_LOT
  - TBL_SFC_PACKAGE.CCUSTOMER_CODE = TBL_BD_CUSTOMER.CUSTOMER_NO
  - TBL_SFC_PACKAGE.CPARENT_ID = TBL_SFC_PACKAGE.CID
  - TBL_SFC_PACKAGE.CSPLIT_ID = TBL_SFC_PACKAGE.CID
  - TBL_SFC_PACKAGE.CLOCATION_ID = TBL_WMS_LOCATION.CID

---

#### 111 包装模板与物料/客户关联表 ( TBL_SFC_PACKAGE_LABEL_LINK )
- **业务含义**：描述了包装模板与物料、客户的绑定关系
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CCUSTOMER_ID | long? | 是 | - | 客户ID，对应TBL_BD_CUSTOMER.CID |
| CITEM_ID | long? | 是 | - | 产品或物料ID  对应 TBL_BD_ITEM.CID |
| CREMARK | string | 是 | - | 备注 |
| CTEMPLATE_ID | long | 否 | - | 模板ID，对应TBL_BD_TEMPLATE.CID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_SFC_PACKAGE_LABEL_LINK.CCUSTOMER_ID = TBL_BD_CUSTOMER.CID
  - TBL_SFC_PACKAGE_LABEL_LINK.CITEM_ID = TBL_BD_ITEM.CID
  - TBL_SFC_PACKAGE_LABEL_LINK.CTEMPLATE_ID = TBL_BD_TEMPLATE.CID

---

#### 112 包装操作日志表 ( TBL_SFC_PACKAGE_LOG )
- **业务含义**：包含包装条码的操作日志
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CBARCODE | string | 是 | - | 包装条码，对应TBL_SFC_PACKAGE.CBARCODE |
| COPERATE_TYPE | int? | 是 | - | 操作类型代码 |
| CREMARK | string | 是 | - | 备注，描述具体的操作类型 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_SFC_PACKAGE_LOG.CBARCODE = TBL_SFC_PACKAGE.CBARCODE

---

#### 113 包装规则主表 ( TBL_SFC_PACKAGE_RULE )
- **业务含义**：包含了所有指定客户的包装规格的信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CBOX_TYPE | string | 是 | - | 箱型 |
| CBOX_WEIGHT | decimal? | 是 | - | 箱重 |
| CDEVIATION | decimal? | 是 | - | 重量偏差 |
| CFAIL_RULE | int? | 是 | - | 失败处理规则 |
| CHEIGHT | decimal? | 是 | - | 高度 |
| CIS_MULTI_CYCLE | string | 是 | - | 是否允许多周期混装，N不允许，Y允许 |
| CIS_MULTI_ITEM | string | 是 | - | 是否允许多料号混装，N不允许，Y允许 |
| CIS_MULTI_LOT | string | 是 | - | 是否允许多批次混装，N不允许，Y允许 |
| CIS_MULTI_ORDER | string | 是 | - | 是否允许多工单混装，N不允许，Y允许 |
| CIS_MULTI_X | string | 是 | - | 是否允许多叉板值混装，N不允许，Y允许 |
| CLEN | decimal? | 是 | - | 长度 |
| CMAX_QTY | decimal? | 是 | - | 最大装箱数量 |
| CMIN_QTY | decimal? | 是 | - | 最小装箱数量 |
| CPKG_WEIGHT | decimal? | 是 | - | 包装重量 |
| CREMARK | string | 是 | - | 备注 |
| CRULE_NAME | string | 是 | - | 规则名称，通常与料号相同 |
| CRULE_TYPE | int | 否 | - | 规则类型 |
| CTOTAL_WEIGHT | decimal? | 是 | - | 总重量 |
| CWIDTH | decimal? | 是 | - | 宽度 |
| CID | long | 否 | - | 主键ID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_SFC_PACKAGE_RULE.CID = TBL_SFC_PACKAGE_RULE_EXT.CPACKAGE_RULE_ID
  - TBL_SFC_PACKAGE_RULE.CID = TBL_SFC_PACKAGE_RULE_LINK.CPACKAGE_RULE_ID

---

#### 114 包装规则扩展配置表 ( TBL_SFC_PACKAGE_RULE_EXT )
- **业务含义**：包含了所有指定客户的包装规格的扩展配置信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CEXTEND_1 | string | 是 | - | 板间隔纸 |
| CEXTEND_10 | string | 是 | - | 有无工艺边 |
| CEXTEND_11 | string | 是 | - | 有无RoHS |
| CEXTEND_12 | string | 是 | - | 纸箱要求 |
| CEXTEND_13 | string | 是 | - | 填充方式 |
| CEXTEND_14 | string | 是 | - | 每箱重量 |
| CEXTEND_15 | string | 是 | - | 特别要求 |
| CEXTEND_16 | string | 是 | - | 封箱方式 |
| CEXTEND_17 | string | 是 | - | 打带方式 |
| CEXTEND_18 | string | 是 | - | 外箱标签 |
| CEXTEND_19 | string | 是 | - | 外箱其他标识 |
| CEXTEND_2 | string | 是 | - | 上下垫板 |
| CEXTEND_20 | string | 是 | - | 其他特别要求 |
| CEXTEND_21 | string | 是 | - | 有无卤素 |
| CEXTEND_22 | string | 是 | - | 有无HF |
| CEXTEND_23 | string | 是 | - | 有无工艺边 |
| CEXTEND_24 | string | 是 | - | 有无RoHS |
| CEXTEND_3 | string | 是 | - | 干燥剂 |
| CEXTEND_4 | string | 是 | - | 湿度卡 |
| CEXTEND_5 | string | 是 | - | 包装方式 |
| CEXTEND_6 | string | 是 | - | 小包标签 |
| CEXTEND_7 | string | 是 | - | 其他特别要求 |
| CEXTEND_8 | string | 是 | - | 有无卤素 |
| CEXTEND_9 | string | 是 | - | 有无HF |
| CIMAGE_DATA | string | 是 | - | 图片 |
| CPACKAGE_RULE_ID | long | 否 | - | 主表ID，对应TBL_SFC_PACKAGE_RULE.CID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_SFC_PACKAGE_RULE_EXT.CPACKAGE_RULE_ID = TBL_SFC_PACKAGE_RULE.CID

---

#### 115 包装规则与物料/客户关联表 ( TBL_SFC_PACKAGE_RULE_LINK )
- **业务含义**：描述了包装规则与物料或客户的关联关系
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CCUSTOMER_ID | long? | 是 | - | 客户ID，对应TBL_BD_CUSTOMER.CID |
| CITEM_ID | long? | 是 | - | 外键，产品或物料ID  对应 TBL_BD_ITEM.CID |
| CPACKAGE_RULE_ID | long? | 是 | - | 包装规则ID，对应TBL_SFC_PACKAGE_RULE.CID |
| CREMARK | string | 是 | - | 备注 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_SFC_PACKAGE_RULE_LINK.CCUSTOMER_ID = TBL_BD_CUSTOMER.CID
  - TBL_SFC_PACKAGE_RULE_LINK.CITEM_ID = TBL_BD_ITEM.CID
  - TBL_SFC_PACKAGE_RULE_LINK.CPACKAGE_RULE_ID = TBL_SFC_PACKAGE_RULE.CID

---

#### 116 不合格工单配方信息表 ( TBL_SFC_RECIPE_LOT )
- **业务含义**：包含VCP电镀工序的参数配方的信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CAPPLY_NO | string | 是 | - | 申请编号 |
| CAUDIT_DESC | string | 是 | - | 审核说明 |
| CAUDIT_TIME | DateTime? | 是 | - | 审核时间 |
| CAUDIT_USER | string | 是 | - | 审核人 |
| CDATETIME_CREATED | DateTime? | 是 | - | 创建时间 |
| CDATETIME_MODIFIED | DateTime? | 是 | - | 修改时间 |
| CENTERPRISE_CODE | long? | 是 | - | 企业代码 |
| CITEM_NAME | string | 是 | - | 料号名称 |
| CORG_CODE | long? | 是 | - | 组织代码 |
| CPROCESS_ID | long? | 是 | - | 工序ID，对应TBL_BD_PROCESS.CID |
| CREMARK | string | 是 | - | 备注 |
| CROWREMARK | string | 是 | - | 行备注 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
| CSTATUS | int? | 是 | - | 审核状态，1已审核，2已驳回，3已失效 |
| CSU_ID | long? | 是 | - | 工作中心ID，对应TBL_BD_WC.CID |
| CUSER_CREATED | string | 是 | - | 创建用户 |
| CUSER_MODIFIED | string | 是 | - | 修改用户 |
| CVERSION | int? | 是 | - | 版本 |
| CID | long | 否 | - | 主键ID |
- **关联关系**：
  - TBL_SFC_RECIPE_LOT.CPROCESS_ID = TBL_BD_PROCESS.CID
  - TBL_SFC_RECIPE_LOT.CSU_ID = TBL_BD_WC.CID
  - TBL_SFC_RECIPE_LOT.CID = TBL_SFC_RECIPE_LOT_LINK.CR_LOT_ID

---

#### 117 不合格工单配方项目明细表 ( TBL_SFC_RECIPE_LOT_LINK )
- **业务含义**：包含VCP电镀工序的参数配方的详细项目信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CDATETIME_CREATED | DateTime? | 是 | - | 创建时间 |
| CDATETIME_MODIFIED | DateTime? | 是 | - | 修改时间 |
| CEXPRESSION | string | 是 | - | 校验表达式 |
| CMAX_TOLERANCE | decimal? | 是 | - | 最大公差 |
| CMAX_VALUE | decimal? | 是 | - | 最大值 |
| CMIN_TOLERANCE | decimal? | 是 | - | 最小公差 |
| CMIN_VALUE | decimal? | 是 | - | 最小值 |
| CORG_CODE | long? | 是 | - | 组织代码 |
| CR_LOT_ID | long | 否 | - | 配方批次主表ID，对应TBL_SFC_RECIPE_LOT.CID |
| CREAL_VALUE | string | 是 | - | 实际值 |
| CREMARK | string | 是 | - | 备注 |
| CRI_DATA_TYPE | string | 是 | - | 数据类型 |
| CRI_DATA_UNIT | string | 是 | - | 数据单位 |
| CRI_DESC | string | 是 | - | 配方项描述 |
| CRI_NAME | string | 是 | - | 配方项名称 |
| CRI_NO | string | 是 | - | 配方项编码 |
| CRI_TYPE | int? | 是 | - | 项目类型 |
| CROWREMARK | string | 是 | - | 行备注 |
| CSEQ | int? | 是 | - | 排序号 |
| CSTANDARD_VALUE | string | 是 | - | 标准值 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
| CUSER_CREATED | string | 是 | - | 创建用户 |
| CUSER_MODIFIED | string | 是 | - | 修改用户 |
| CVALUE_TYPE | int? | 是 | - | 值类型 |
- **关联关系**：
  - TBL_SFC_RECIPE_LOT_LINK.CR_LOT_ID = TBL_SFC_RECIPE_LOT.CID

---

#### 118 按产品维度的配方信息主表 ( TBL_SFC_RECIPE_PRODUCT )
- **业务含义**：包含VCP电镀工序的以产品为单位的参数配方的信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CAUDIT_DESC | string | 是 | - | 审核说明 |
| CAUDIT_TIME | DateTime? | 是 | - | 审核时间 |
| CAUDIT_USER | string | 是 | - | 审核人 |
| CDATETIME_CREATED | DateTime? | 是 | - | 创建时间 |
| CDATETIME_MODIFIED | DateTime? | 是 | - | 修改时间 |
| CDD_TYPE | string | 是 | - | 打点类型 |
| CENTERPRISE_CODE | long? | 是 | - | 企业代码 |
| CID | long | 否 | - | 主键ID |
| CINSTANCE_ID | string | 是 | - | 实例ID |
| CITEM_ID | long | 否 | - | 外键，产品或物料ID  对应 TBL_BD_ITEM.CID |
| CORG_CODE | long? | 是 | - | 组织代码 |
| CPROCESS_ID | long? | 是 | - | 工序ID，对应TBL_BD_PROCESS.CID |
| CREMARK | string | 是 | - | 备注 |
| CROWREMARK | string | 是 | - | 行备注 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
| CSTATUS | int? | 是 | - | 审核状态 |
| CSU_ID | long | 否 | - | 工作中心ID，对应TBL_BD_WC.CID |
| CSU_R_ID | long | 否 | - | 设备配方ID，对应TBL_SFC_RECIPE_SMART_UNIT.CID |
| CUSER_CREATED | string | 是 | - | 创建用户 |
| CUSER_MODIFIED | string | 是 | - | 修改用户 |
| CVERSION | int? | 是 | - | 版本 |
- **关联关系**：
  - TBL_SFC_RECIPE_PRODUCT.CITEM_ID = TBL_BD_ITEM.CID
  - TBL_SFC_RECIPE_PRODUCT.CPROCESS_ID = TBL_BD_PROCESS.CID
  - TBL_SFC_RECIPE_PRODUCT.CSU_ID = TBL_BD_WC.CID
  - TBL_SFC_RECIPE_PRODUCT.CID = TBL_SFC_RECIPE_PRODUCT_LINK.CR_PRODUCT_ID
  - TBL_SFC_RECIPE_PRODUCT.CSU_R_ID = TBL_SFC_RECIPE_SMART_UNIT.CID

---

#### 119 产品配方项目明细表 ( TBL_SFC_RECIPE_PRODUCT_LINK )
- **业务含义**：包含VCP电镀工序的以产品为单位的参数配方的详细项目信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CDATETIME_CREATED | DateTime? | 是 | - | 创建时间 |
| CDATETIME_MODIFIED | DateTime? | 是 | - | 修改时间 |
| CENTERPRISE_CODE | long? | 是 | - | 企业代码 |
| CEXPRESSION | string | 是 | - | 校验表达式 |
| CID | long | 否 | - | 主键ID |
| CINSTANCE_ID | string | 是 | - | 实例ID |
| CMAX_TOLERANCE | decimal? | 是 | - | 最大公差 |
| CMAX_VALUE | decimal? | 是 | - | 最大值 |
| CMIN_TOLERANCE | decimal? | 是 | - | 最小公差 |
| CMIN_VALUE | decimal? | 是 | - | 最小值 |
| CORG_CODE | long? | 是 | - | 组织代码 |
| CR_PRODUCT_ID | long | 否 | - | 产品配方主表ID，对应TBL_SFC_RECIPE_PRODUCT.CID |
| CREAL_VALUE | string | 是 | - | 实际值 |
| CREMARK | string | 是 | - | 备注 |
| CRI_DATA_TYPE | string | 是 | - | 数据类型 |
| CRI_DATA_UNIT | string | 是 | - | 数据单位 |
| CRI_DESC | string | 是 | - | 配方项描述 |
| CRI_NAME | string | 是 | - | 配方项名称 |
| CRI_NO | string | 是 | - | 配方项编码 |
| CRI_TYPE | int? | 是 | - | 项目类型 |
| CROWREMARK | string | 是 | - | 行备注 |
| CSEQ | int? | 是 | - | 排序号 |
| CSTANDARD_VALUE | string | 是 | - | 标准值 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
| CUSER_CREATED | string | 是 | - | 创建用户 |
| CUSER_MODIFIED | string | 是 | - | 修改用户 |
| CVALUE_TYPE | int? | 是 | - | 值类型 |
- **关联关系**：
  - TBL_SFC_RECIPE_PRODUCT_LINK.CR_PRODUCT_ID = TBL_SFC_RECIPE_PRODUCT.CID

---

#### 120 生产记录表 ( TBL_SFC_WS_LOG )
- **业务含义**：以工序为单位记录某张工单在某个设备上的生产记录信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| BOARD_TYPE | string | 是 | - | 板类型 |
| CCHECK_REMARK | string | 是 | - | 审核备注 |
| CCHECK_TIME | DateTime? | 是 | - | 审核时间 |
| CCHECK_USER_NAME | string | 是 | - | 审核人账号，对应TBL_SYS_USER.CUSER_NAME |
| CEND_TIME | DateTime? | 是 | - | 完工时间 |
| CEND_USER_NAME | string | 是 | - | 完工人账号，对应TBL_SYS_USER.CUSER_NAME |
| CIS_CHECK | string | 是 | - | 是否已审核 |
| CIS_FINISH | string | 是 | - | 是否完工 |
| CIS_WIP | string | 是 | - | 是否已过数 |
| CITEM_ID | long? | 是 | - | 外键，产品或物料ID  对应 TBL_BD_ITEM.CID |
| CLEVEL | string | 是 | - | 等级 |
| CMO_LOT | string | 是 | - | 工单批次 |
| CNG_NUMBER | decimal? | 是 | - | 不良数量 |
| CNUMBER_TYPE | int? | 是 | - | 数量类型 |
| CPROCESS_ID | long | 否 | - | 工序ID，对应TBL_BD_PROCESS.CID |
| CREMARK | string | 是 | - | 备注 |
| CSCAN_BARCODE | string | 是 | - | 扫描条码，对应TBL_MO.CMO_LOT |
| CSCRAP_NUMBER | decimal? | 是 | - | 报废数量 |
| CSHIFT | string | 是 | - | 班次 |
| CSTART_TIME | DateTime? | 是 | - | 开工时间 |
| CSTART_USER_NAME | string | 是 | - | 开工人账号，对应TBL_SYS_USER.CUSER_NAME |
| CSTATUS | int? | 是 | - | 0待审核、1已通过、2已驳回 |
| CTEMPLATE_ID | long | 否 | - | 模板ID，对应TBL_NP_TEMPLATE.CID |
| CUNIT | string | 是 | - | 单位 |
| CUSTOMER_CODE | string | 是 | - | 客户编码，对应TBL_BD_CUSTOMER.CUSTOMER_NO |
| CWC_ID | long | 否 | - | 工作中心ID，对应TBL_BD_WC.CID |
| CWORK_NUMBER | decimal | 否 | - | 工作数量 |
| CWORK_TYPE | int | 否 | - | 1:正常生产记录(检验生产记录);2:批量生产记录;3:无工单生产记录;4:历史记录新增;5:FQC生产记录 |
| CID | long | 否 | - | 主键ID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_SFC_WS_LOG.CITEM_ID = TBL_BD_ITEM.CID
  - TBL_SFC_WS_LOG.CPROCESS_ID = TBL_BD_PROCESS.CID
  - TBL_SFC_WS_LOG.CTEMPLATE_ID = TBL_NP_TEMPLATE.CID
  - TBL_SFC_WS_LOG.CWC_ID = TBL_BD_WC.CID
  - TBL_SFC_WS_LOG.CUSTOMER_CODE = TBL_BD_CUSTOMER.CUSTOMER_NO
  - TBL_SFC_WS_LOG.CMO_LOT = TBL_MO.CMO_LOT
  - TBL_SFC_WS_LOG.CCHECK_USER_NAME = TBL_SYS_USER.CUSER_NAME
  - TBL_SFC_WS_LOG.CEND_USER_NAME = TBL_SYS_USER.CUSER_NAME
  - TBL_SFC_WS_LOG.CSTART_USER_NAME = TBL_SYS_USER.CUSER_NAME
  - TBL_SFC_WS_LOG.CID = TBL_SFC_WS_LOG_ITEM.CWS_LOG_ID
  - TBL_SFC_WS_LOG.CSCAN_BARCODE = TBL_MO.CMO_LOT

---

#### 121 生产记录项目明细 ( TBL_SFC_WS_LOG_ITEM )
- **业务含义**：记录某条生产记录中包含的详细生产相关参数值信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CALARM_MAX_VALUE | decimal? | 是 | - | 预警上限 |
| CALARM_MIN_VALUE | decimal? | 是 | - | 预警下限 |
| CINPUT_VALUE | string | 是 | - | 输入值 |
| CREMARK | string | 是 | - | 备注 |
| CRESULT | int | 否 | - | 结果 |
| CSEQ | int | 否 | - | 排序号 |
| CSTANDARD_MAX_ALLOW | string | 是 | - | 标准上限是否允许等于 |
| CSTANDARD_MAX_VALUE | decimal? | 是 | - | 标准上限 |
| CSTANDARD_MIN_ALLOW | string | 是 | - | 标准下限是否允许等于 |
| CSTANDARD_MIN_VALUE | decimal? | 是 | - | 标准下限 |
| CSTANDARD_VALUE | string | 是 | - | 标准值 |
| CSTANDARD_VALUE_TYPE | int | 否 | - | 标准值类型 |
| CTEMPLATE_ITEM_CODE | string | 是 | - | 模板项编码 |
| CTEMPLATE_ITEM_DESC | string | 是 | - | 模板项描述 |
| CTEMPLATE_ITEM_NAME | string | 是 | - | 模板项名称 |
| CTEMPLATE_ITEM_TAG | string | 是 | - | 模板项标签 |
| CUNIT | string | 是 | - | 单位 |
| CWS_LOG_ID | long | 否 | - | 生产记录主表ID，对应TBL_SFC_WS_LOG.CID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_SFC_WS_LOG_ITEM.CWS_LOG_ID = TBL_SFC_WS_LOG.CID

---

#### 122 工位报工模板配置表 ( TBL_SFC_WS_TEMPLATE_CONFIG )
- **业务含义**：记录了关于生产记录模板的配置信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CFIRST_COMMIT_TIMESPAN | int? | 是 | - | 一次报工自动补全时间差（min），Y代表是，N代表否 |
| CIS_AUTO_GET_NUMBER | string | 是 | - | 是否自动获取数量，Y代表是，N代表否 |
| CIS_CONTROL_NUMBER | string | 是 | - | 是否管控数量，Y代表是，N代表否 |
| CIS_FIRST_COMMIT | string | 是 | - | 是否一次报工，Y代表是，N代表否 |
| CIS_GET_LAST_DATA | string | 是 | - | 是否赋值上次记录，Y代表是，N代表否 |
| CIS_IGNORE_ITEM | string | 是 | - | 赋值上次记录时是否忽略产品，Y代表是，N代表否 |
| CIS_IPQC_FIRST | string | 是 | - | 是否需要IPQC首件管控，Y代表是，N代表否 |
| CIS_KEYPART_MANAGE | string | 是 | - | 是否关键物料管控，Y代表是，N代表否 |
| CIS_LOCK_NUMBER | string | 是 | - | 是否锁定数量，Y代表是，N代表否 |
| CIS_NO_ORDER | string | 是 | - | 是否允许无工单生产记录，Y代表是，N代表否 |
| CIS_PM | string | 是 | - | 是否校验设备点检，Y代表是，N代表否 |
| CIS_WIP_TEMPLATE | string | 是 | - | 是否过数模板，Y代表是，N代表否 |
| CNEXT_TIMESPAN | int? | 是 | - | 相同lot卡下一次开工最小时间间隔（min） |
| COVERDUE_TIME | int? | 是 | - | 超期时间 |
| CREMARK | string | 是 | - | 备注 |
| CSE_TIMESPAN | int? | 是 | - | 开工完工最小时间间隔（min） |
| CTEMPLATE_ID | long | 否 | - | 模板ID，对应TBL_NP_TEMPLATE.CID |
| CUNIT | string | 是 | - | 默认单位 |
| CWARNING_TIME | int? | 是 | - | 预警时间 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_SFC_WS_TEMPLATE_CONFIG.CTEMPLATE_ID = TBL_NP_TEMPLATE.CID

---

#### 123 工作中心与模板关联配置表 ( TBL_SFC_WS_TEMPLATE_LINK )
- **业务含义**：记录了工作中心与生产记录模板关联的信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CPROCESS_ID | long | 否 | - | 工序ID，对应TBL_BD_PROCESS.CID |
| CREMARK | string | 是 | - | 备注 |
| CTEMPLATE_ID | long | 否 | - | 模板ID，对应TBL_NP_TEMPLATE.CID |
| CWC_ID | long | 否 | - | 工作中心ID，对应TBL_BD_WC.CID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_SFC_WS_TEMPLATE_LINK.CPROCESS_ID = TBL_BD_PROCESS.CID
  - TBL_SFC_WS_TEMPLATE_LINK.CTEMPLATE_ID = TBL_NP_TEMPLATE.CID
  - TBL_SFC_WS_TEMPLATE_LINK.CWC_ID = TBL_BD_WC.CID

---

#### 124 工单信息表 ( TBL_MO )
- **业务含义**：记录了所有工单的相关信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CACTULA_END_TIME | DateTime? | 是 | - | 实际完成时间 |
| CACTULA_START_TIME | DateTime? | 是 | - | 实际生产时间 |
| CCOMPLETED_QTY | decimal? | 是 | - | 完工数量 |
| CITEM_ID | long? | 是 | - | 外键，产品ID  对应 TBL_BD_ITEM.CID |
| CLEVEL | int? | 是 | - | 级别 |
| CMO_LOT | string | 是 | - | 工单批次 |
| CORDER_DATETIME | DateTime? | 是 | - | 工单日期 |
| CORDER_NO | string | 是 | - | 工单编号 |
| CPARENT_ID | string | 是 | - | 父级工单编号 |
| CPLAN_END_TIME | DateTime? | 是 | - | 预计完成时间 |
| CPLAN_QTY | decimal? | 是 | - | 计划数量 |
| CPLAN_START_TIME | DateTime? | 是 | - | 预计生产时间 |
| CREMARK | string | 是 | - | 备注 |
| CROUTE_ID | long? | 是 | - | 工艺路线ID |
| CSCHEDULE_QTY | decimal? | 是 | - | 已排产数量 |
| CSEQ | int? | 是 | - | 工单批次中的顺序 |
| CSOURCE_ID | string | 是 | - | 来源ID |
| CSOURCE_ORDER_NO | string | 是 | - | 来源工单编号 |
| CSTATUS | int? | 是 | - | 工单状态，2：已发放；7：外协；6：已暂停；5：已取消 |
| CUST_CODE | string | 是 | - | 客户代码 |
| CWC_ID | long? | 是 | - | 工作中心ID，对应TBL_BD_WC.CID |
| CID | long | 否 | - | 主键ID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_MO.CITEM_ID = TBL_BD_ITEM.CID
  - TBL_MO.CWC_ID = TBL_BD_WC.CID
  - TBL_MO.CMO_LOT = TBL_EAP_ALARM.CORDER_NO
  - TBL_MO.CMO_LOT = TBL_EAP_GE_PARAM_USE_LOG.CWO
  - TBL_MO.CMO_LOT = TBL_EAP_LDI_LOG.CORDER_NO
  - TBL_MO.CMO_LOT = TBL_EAP_LWT_DETECTIONS.CLOT_NO
  - TBL_MO.CMO_LOT = TBL_EAP_MASON_DETECTIONS_DTL.CLOT_NO
  - TBL_MO.CMO_LOT = TBL_EAP_PMS_PROD.CWON
  - TBL_MO.CMO_LOT = TBL_EAP_YUHUI_TEST_RECORDS.CORDER_NO
  - TBL_MO.CMO_LOT = TBL_QM_PL_LOG.CMO_LOT
  - TBL_MO.CMO_LOT = TBL_SFC_PACKAGE.CMO_LOT
  - TBL_MO.CMO_LOT = TBL_SFC_WS_LOG.CMO_LOT
  - TBL_MO.CMO_LOT = TBL_MO_OUTS.CMO_LOT
  - TBL_MO.CMO_LOT = VW_ERP_MO_DATE_CODE.CORDER_NO
  - TBL_MO.CMO_LOT = VW_MO_ROUTE.CORDER_NO
  - TBL_MO.CID = TBL_MO_BARCODE_PROD_LINK.CMO_ID

---

#### 125 外协工单信息表 ( TBL_MO_OUTS )
- **业务含义**：记录了外协工单的相关信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CITEM_NO | string | 是 | - | 料号，对应TBL_BD_ITEM.CITEM_NO |
| CMO_LOT | string | 是 | - | 工单批次号，对应TBL_MO.CMO_LOT |
| COS_NO | string | 是 | - | 外协订单号，对应VW_ERP_OUTSOURCED_PO.外协订单号 |
| CQTY | int | 否 | - | 数量 |
| CSO_NO | string | 是 | - | 销售订单号，对应VW_ERP_OUTSOURCED_PO.销售订单号 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_MO_OUTS.CMO_LOT = TBL_MO.CMO_LOT
  - TBL_MO_OUTS.CITEM_NO = TBL_BD_ITEM.CITEM_NO

---

#### 126 外协班次员工配置表 ( TBL_OUTSOURCE_SHIFT_EMPLOYEE )
- **业务含义**：包含外协工序对应员工和班次的配置信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CREATED_TIME | string | 是 | - | 创建时间 |
| CWC_ID | long | 否 | - | 工作中心ID，对应TBL_BD_WC.CID |
| ID | int | 否 | - | 主键ID |
| SHIFT_CODE | string | 是 | - | 班次编码，值为白班和晚班 |
| UPDATED_TIME | string | 是 | - | 更新时间 |
| USER_ID | long | 否 | - | 员工用户ID，对应TBL_SYS_USER.CID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_OUTSOURCE_SHIFT_EMPLOYEE.CWC_ID = TBL_BD_WC.CID
  - TBL_OUTSOURCE_SHIFT_EMPLOYEE.USER_ID = TBL_SYS_USER.CID

---

#### 127 ERP外协订单和料号 ( VW_ERP_OUTSOURCED_PO )
- **业务含义**：包含ERP中外协订单号和料号的关联关系
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| 供应商代码 | string | 是 | - | 供应商代码 |
| 供应商名称 | string | 是 | - | 供应商名称 |
| 销售订单号 | string | 是 | - | 销售订单号 |
| 外协订单号 | string | 是 | - | 外协订单号 |
| 生产编号 | string | 是 | - | 生产编号 |
| 数量 | int | 否 | - | 数量 |
| 订单状态 | string | 是 | - | 订单状态，Outsoucing：外协中；Shipped：已发货；Cancel：已取消；Close：已关闭；Valid：生效中 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：无

---

#### 128 物料详细参数视图 ( VIEW_Core_Materials )
- **业务含义**：包含具体物料代码的相关参数信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| 物料代码 | string | 是 | - | 物料代码 |
| 物料名称 | string | 是 | - | 物料名称 |
| 物料规格 | string | 是 | - | 物料规格 |
| 材料类型 | string | 是 | - | 材料类型 |
| 颜色 | string | 是 | - | 板芯颜色 |
| 高 | string | 是 | - | 高 |
| 是否含铜 | string | 是 | - | 0：不含铜；1：含铜 |
| 上铜 | string | 是 | - | 上铜 |
| 下铜 | string | 是 | - | 下铜 |
| TG值 | string | 是 | - | TG值 |
| CTI | string | 是 | - | CTI |
| 无卤素 | string | 是 | - | 0：有卤素；1：无卤素 |
| 水印 | string | 是 | - | 0：无水印；1：有水印 |
| 长 | decimal | 否 | - | 长 |
| 宽 | decimal | 否 | - | 宽 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：无

---

#### 129 ERP 发料信息视图 ( VM_ERP_MI_INFO )
- **业务含义**：包含ERP中具体的发料信息记录
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| ProductID | string | 是 | - | 产品编号，对应TBL_BD_ITEM.CITEM_NO |
| id | string | 是 | - | 记录标识 |
| woNumber | string | 是 | - | 工单号，对应TBL_MO.CMO_LOT |
| Unit | string | 是 | - | 单位 |
| ProcessID | string | 是 | - | 工序编号，对应TBL_BD_PROCESS.CPROCESS_NO |
| code | string | 是 | - | 编码 |
| SuppBatchNo | string | 是 | - | 供应商批次号 |
| nextStep | string | 是 | - | 下一步骤 |
| nextProcessId | string | 是 | - | 下一工序编号 |
| ifBarcodEntry | string | 是 | - | 是否条码进站 |
| WoCreateDate | DateTime? | 是 | - | 工单创建日期 |
| SETperPCS | string | 是 | - | 每 PCS 的 SET 数 |
| PNLperPCS | string | 是 | - | 每 PCS 的 PNL 数 |
| culayers | string | 是 | - | 铜层数 |
| PwParentId | string | 是 | - | 父工单标识 |
| WipPcs | string | 是 | - | 在制 PCS 数 |
| WipPNL | string | 是 | - | 在制 PNL 数 |
| ZCPcs | string | 是 | - | 转出 PCS 数 |
| ZCPnl | string | 是 | - | 转出 PNL 数 |
| WXPcs | string | 是 | - | 维修 PCS 数 |
| WXPnl | string | 是 | - | 维修 PNL 数 |
| parentId | string | 是 | - | 工单 ID |
| moId | string | 是 | - | 流程标识 |
| PwId | string | 是 | - | 工序序号 |
| processNumber | string | 是 | - | 工单工艺路线 ID |
| moRouteId | string | 是 | - | 计划 PCS 数 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：无

---

#### 130 ERP 工单日期码视图 ( VW_ERP_MO_DATE_CODE )
- **业务含义**：包含每张工单对应的日期码
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CORDER_NO | string | 是 | - | 工单号，对应TBL_MO.CMO_LOT |
| CPROCESS_NO | string | 是 | - | 工序编号，对应TBL_BD_PROCESS.CPROCESS_NO |
| CPROCESS_NAME | string | 是 | - | 工序名称 |
| CDATE_CODE | string | 是 | - | 日期码 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - VW_ERP_MO_DATE_CODE.CORDER_NO = TBL_MO.CMO_LOT
  - VW_ERP_MO_DATE_CODE.CPROCESS_NO = TBL_BD_PROCESS.CPROCESS_NO

---

#### 131 MI工序通用参数视图 ( VW_MI_PROCESS_GENERAL )
- **业务含义**：描述所有料号的对应工序包含的参数值
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| ProductID | string | 是 | - | 产品编号，对应TBL_BD_ITEM.CITEM_NO |
| ProcessID | string | 是 | - | 工序编号，对应TBL_BD_PROCESS.CPROCESS_NO |
| ParamID | string | 是 | - | 参数编号 |
| ParamName | string | 是 | - | 参数名称 |
| ParamValue | string | 是 | - | 参数值（板厚） |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - VW_MI_PROCESS_GENERAL.CITEM_NO = TBL_BD_ITEM.CITEM_NO
  - VW_MI_PROCESS_GENERAL.CPROCESS_NO = TBL_BD_PROCESS.CPROCESS_NO

---

#### 132 工单工艺路线视图 ( VW_MO_ROUTE )
- **业务含义**：描述工单需要经过的工艺路线信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CORDER_NO | string | 是 | - | 工单号，对应TBL_MO.CMO_LOT |
| CITEM_NO | string | 是 | - | 产品编号，对应TBL_BD_ITEM.CITEM_NO |
| CPROCESS_NO | string | 是 | - | 工序编号，对应TBL_BD_PROCESS.CPROCESS_NO |
| CPROCESS_NAME | string | 是 | - | 工序名称 |
| CSEQ | string | 是 | - | 工序顺序 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - VW_MO_ROUTE.CORDER_NO = TBL_MO.CMO_LOT
  - VW_MO_ROUTE.CITEM_NO = TBL_BD_ITEM.CITEM_NO
  - VW_MO_ROUTE.CPROCESS_NO = TBL_BD_PROCESS.CPROCESS_NO

---

#### 133 在线在制品工单统计视图 ( VW_WIP_Online )
- **业务含义**：包含所有的在线的工单列表
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| ProductID | string | 是 | - | 产品编号，对应TBL_BD_ITEM.CITEM_NO |
| FlowCardNo | string | 是 | - | 工单号，对应TBL_MO.CMO_LOT |
| ProcessID | string | 是 | - | 工序编号，对应TBL_BD_PROCESS.CPROCESS_NO |
| Wip | int | 否 | - | 在制 PCS 数 |
| PANELS | int | 否 | - | 在制 PNL 数 |
| SETS_QTY | int | 否 | - | SET数 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：无

---

### 2.9 仓储管理

> 本章节数据来源于 Excel 工作表：`仓储管理`

#### 134 物料条码表 ( TBL_WMS_ITEM_BARCODE )
- **业务含义**：包含物料供应商在MES系统中打印的物料条码列表
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CBALANCE_QTY | decimal? | 是 | - | 剩余数量 |
| CBARCODE | string | 是 | - | 物料条码 |
| CBARCODE_TYPE | string | 是 | - | 条码类型 |
| CCYCLE | string | 是 | - | 周期 |
| CEFFECTIVE_STATUS | int? | 是 | - | 是否超期；1：未超期； 2：已超期 |
| CERP_LOT_NO | string | 是 | - | ERP批次号 |
| CEXPIRATION_TIME | DateTime? | 是 | - | 有效日期 |
| CITEM_ID | long? | 是 | - | 外键，物料ID  对应TBL_BD_ITEM.CID |
| CLOCATION_ID | long? | 是 | - | 货位ID，对应TBL_WMS_LOCATION.CID |
| CLOSS_QTY | decimal? | 是 | - | 调整数量 |
| CLOT_NO | string | 是 | - | 批次号 |
| CPACKING_DATETIME | DateTime? | 是 | - | 包箱时间 |
| CPACKING_ID | long? | 是 | - | 包装条码ID，对应TBL_WMS_ITEM_PACKING_BARCODE.CID |
| CPLAIN_CODE | string | 是 | - | 料盘编码 |
| CPRINT_TIMES | int? | 是 | - | 打印次数 |
| CPRODUCTION_DATETIME | DateTime? | 是 | - | 生产时间 |
| CQTY | decimal? | 是 | - | 条码数量 |
| CREMARK | string | 是 | - | 备注 |
| CSCRAP_TIME | DateTime? | 是 | - | 条码报废时间 |
| CSO_NO | string | 是 | - | 销售订单 |
| CSOURCE_ID | long? | 是 | - | 来源ID，对应TBL_SRM_PO_DETAIL.CID |
| CSPLIT_DATETIME | DateTime? | 是 | - | 拆分时间 |
| CSPLIT_ID | long | 否 | - | 上级条码ID，对应TBL_WMS_ITEM_BARCODE.CID |
| CSRC_ID | long? | 是 | - | 来源记录ID（这里保存的是采购订单交付表的ID） |
| CSRC_TYPE | string | 是 | - | 来源类型 |
| CSTATUS | string | 是 | - | 条码状态；BARCODE_SCRAP：已报废；BARCODE_SEND：已发料；BARCODE_STOCK：已入库；BARCODE_SUPPLIER：在供应商 |
| CSTORAGE_TIME | DateTime? | 是 | - | 入库日期 |
| CSUPPLIER_ID | long? | 是 | - | 供应商ID，对应TBL_BD_SUPPLIER.CID |
| CSUPPLIER_LOT_NO | string | 是 | - | 供应商批号 |
| CUNIT | string | 是 | - | 单位 |
| CUSE_QTY | decimal? | 是 | - | 使用数量 |
| CID | long | 否 | - | 主键 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_WMS_ITEM_BARCODE.CITEM_ID = TBL_BD_ITEM.CID
  - TBL_WMS_ITEM_BARCODE.CSUPPLIER_ID = TBL_BD_SUPPLIER.CID
  - TBL_WMS_ITEM_BARCODE.CLOCATION_ID = TBL_WMS_LOCATION.CID
  - TBL_WMS_ITEM_BARCODE.CPACKING_ID = TBL_WMS_ITEM_PACKING_BARCODE.CID
  - TBL_WMS_ITEM_BARCODE.CSPLIT_ID = TBL_WMS_ITEM_BARCODE.CID
  - TBL_WMS_ITEM_BARCODE.CSRC_ID = TBL_SRM_PO_DELIVERY.CID
  - TBL_WMS_ITEM_BARCODE.CBARCODE = TBL_SRM_RECEIVING_BARCODE.CBARCODE
  - TBL_WMS_ITEM_BARCODE.CID = TBL_WMS_PICKING_LOG_DTL.CBARCODE_ID
  - TBL_WMS_ITEM_BARCODE.CID = TBL_WMS_BARCODE_SPLIT_RECORD.CSOURCE_BARCODE_ID
  - TBL_WMS_ITEM_BARCODE.CID = TBL_WMS_BARCODE_SPLIT_RECORD.CTARGET_BARCODE_ID
  - TBL_WMS_ITEM_BARCODE.CID = TBL_WMS_STOCK_BARCODE_LINK.CBARCODE_ID
  - TBL_WMS_ITEM_BARCODE.CID = TBL_MO_BARCODE_PROD_LINK.CBARCODE_ID
  - TBL_WMS_ITEM_BARCODE.CSOURCE_ID = TBL_SRM_PO_DETAIL.CID

---

#### 135 物料包装条码表 ( TBL_WMS_ITEM_PACKING_BARCODE )
- **业务含义**：包含物料供应商在MES系统中打印的包装箱条码列表
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CBARCODE | string | 是 | - | 包装条码 |
| CPARENT_ID | long | 否 | - | 上级包装ID，对应TBL_WMS_ITEM_PACKING_BARCODE.CID |
| CREMARK | string | 是 | - | 备注 |
| CSOURCE_ID | string | 是 | - | 来源ID |
| CID | long | 否 | - | 主键 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_WMS_ITEM_PACKING_BARCODE.CPARENT_ID = TBL_WMS_ITEM_PACKING_BARCODE.CID
  - TBL_WMS_ITEM_PACKING_BARCODE.CID = TBL_WMS_ITEM_BARCODE.CPACKING_ID

---

#### 136 线别仓操作记录 ( TBL_WMS_LINE_RECORD )
- **业务含义**：包含线边仓中的物料的操作记录信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CATTRIBUTE | string | 是 | - | 属性 |
| CIN_TIME | DateTime? | 是 | - | 入仓时间 |
| CIN_USER | string | 是 | - | 入仓人，对应TBL_SYS_USER.CUSER_NAME |
| CITEM_NAME | string | 是 | - | 产品 |
| CLOCATION_SN | string | 是 | - | 货位条码，对应TBL_WMS_LOCATION.CLOCATION_SN |
| CORDER_NO | string | 是 | - | 工单号，对应TBL_MO.CMO_LOT |
| COUT_QTY | int? | 是 | - | 已出仓数量 |
| COUT_TIME | DateTime? | 是 | - | 出仓时间 |
| COUT_USER | string | 是 | - | 出仓人，对应TBL_SYS_USER.CUSER_NAME |
| CPROCESS | string | 是 | - | 工艺，对应TBL_BD_PROCESS.CPROCESS_NAME |
| CQTY | int? | 是 | - | 数量 |
| CREMARK | string | 是 | - | 备注 |
| CSTATUS | int | 否 | - | 1已入仓、2已出仓 |
| CTG_VALUE | string | 是 | - | TG值 |
| CWAREHOUSE_ID | long | 否 | - | 中转仓ID，对应TBL_WMS_WAREHOUSE.CID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_WMS_LINE_RECORD.CLOCATION_SN = TBL_WMS_LOCATION.CLOCATION_SN
  - TBL_WMS_LINE_RECORD.CWAREHOUSE_ID = TBL_WMS_WAREHOUSE.CID
  - TBL_WMS_LINE_RECORD.CORDER_NO = TBL_MO.CMO_LOT
  - TBL_WMS_LINE_RECORD.CPROCESS = TBL_BD_PROCESS.CPROCESS_NAME
  - TBL_WMS_LINE_RECORD.CIN_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_WMS_LINE_RECORD.COUT_USER = TBL_SYS_USER.CUSER_NAME

---

#### 137 仓库货位 ( TBL_WMS_LOCATION )
- **业务含义**：包含仓库货位与仓库的关联关系信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CLOCATION_SN | string | 是 | - | 货位编码/货位条码 |
| CWAREHOUSE_ID | long | 否 | - | 仓库ID，对应TBL_WMS_WAREHOUSE.CID |
| CID | long | 否 | - | 主键 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_WMS_LOCATION.CWAREHOUSE_ID = TBL_WMS_WAREHOUSE.CID
  - TBL_WMS_LOCATION.CID = TBL_WMS_ITEM_BARCODE.CLOCATION_ID
  - TBL_WMS_LOCATION.CLOCATION_SN = TBL_WMS_LINE_RECORD.CLOCATION_SN
  - TBL_WMS_LOCATION.CLOCATION_SN = TBL_WMS_MANTISSA_RECORD.CLOCATION_SN
  - TBL_WMS_LOCATION.CID = TBL_SRM_RECEIVING_DTL.CLOCATION_ID

---

#### 138 尾数仓操作记录 ( TBL_WMS_MANTISSA_RECORD )
- **业务含义**：包含尾数仓中的物料的操作记录信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CBARCODE | string | 是 | - | 条码 |
| CCYCLE | string | 是 | - | 周期 |
| CIN_TIME | DateTime? | 是 | - | 入仓时间 |
| CIN_USER | string | 是 | - | 入仓人，对应TBL_SYS_USER.CUSER_NAME |
| CITEM_NAME | string | 是 | - | 产品，对应TBL_BD_ITEM.CITEM_NAME |
| CLOCATION_SN | string | 是 | - | 货位条码，对应TBL_WMS_LOCATION.CLOCATION_SN |
| COUT_QTY | int? | 是 | - | 已出仓数量 |
| COUT_TIME | DateTime? | 是 | - | 出仓时间 |
| COUT_USER | string | 是 | - | 出仓人，对应TBL_SYS_USER.CUSER_NAME |
| CQTY | int? | 是 | - | 数量 |
| CREMARK | string | 是 | - | 备注 |
| CSTATUS | int | 否 | - | 1已入仓、2已出仓 |
| CWAREHOUSE_ID | long | 否 | - | 尾数仓ID，对应TBL_WMS_WAREHOUSE.CID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_WMS_MANTISSA_RECORD.CLOCATION_SN = TBL_WMS_LOCATION.CLOCATION_SN
  - TBL_WMS_MANTISSA_RECORD.CWAREHOUSE_ID = TBL_WMS_WAREHOUSE.CID
  - TBL_WMS_MANTISSA_RECORD.CIN_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_WMS_MANTISSA_RECORD.COUT_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_WMS_MANTISSA_RECORD.CITEM_NAME = TBL_BD_ITEM.CITEM_NAME

---

#### 139 MES领料记录 ( TBL_WMS_PICKING_LOG )
- **业务含义**：包含MES系统中的领料记录(与ERP领料记录不同)
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CPICKING_CODE | string | 是 | - | 领料单号 |
| CPICKING_QTY | decimal? | 是 | - | 领料数量 |
| CREMARK | string | 是 | - | 备注 |
| CUSER_NAME | string | 是 | - | 领料人，对应TBL_SYS_USER.CUSER_NAME |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_WMS_PICKING_LOG.CUSER_NAME = TBL_SYS_USER.CUSER_NAME
  - TBL_WMS_PICKING_LOG.CID = TBL_WMS_PICKING_LOG_DTL.CPICKING_ID

---

#### 140 领料记录明细 ( TBL_WMS_PICKING_LOG_DTL )
- **业务含义**：包含MES系统中的领料记录明细信息(与ERP领料记录不同)
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CBARCODE_ID | long? | 是 | - | 条码ID，对应TBL_WMS_ITEM_BARCODE.CID |
| CPICKING_ID | long? | 是 | - | 领料主表ID |
| CQTY | decimal? | 是 | - | 领料数量 |
| CREMARK | string | 是 | - | 备注 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_WMS_PICKING_LOG_DTL.CBARCODE_ID = TBL_WMS_ITEM_BARCODE.CID
  - TBL_WMS_PICKING_LOG_DTL.CPICKING_ID = TBL_WMS_PICKING_LOG.CID

---

#### 141 仓库主数据表 ( TBL_WMS_WAREHOUSE )
- **业务含义**：包含了仓库列表信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CWAREHOUSE_CODE | string | 是 | - | 仓库编码 |
| CWAREHOUSE_NAME | string | 是 | - | 仓库名称 |
| CWAREHOUSE_TYPE_ID | long? | 是 | - | 仓库类型ID，对应TBL_WMS_WAREHOUSE_TYPE.CID |
| CID | long | 否 | - | 主键 |
| CDEPARTMENT_CODE | string | 是 | - | 部门编码 |
| CIS_BATCH | string | 是 | - | 是否批号，Y：是；N：否 |
| CIS_POSITION | string | 是 | - | 是否货位，Y：是；N：否 |
| CIS_PRINT | string | 是 | - | 是否打条码，Y：是；N：否 |
| CPERSON_ID | string | 是 | - | 管理员ID |
| CREMARK | string | 是 | - | 备注 |
| CSOURCE_ID | string | 是 | - | 来源ID |
| CWAREHOUSE_ADDRESS | string | 是 | - | 地址 |
| CWAREHOUSE_CODE | string | 是 | - | 仓库编码 |
| CWAREHOUSE_NAME | string | 是 | - | 仓库名称 |
| CWAREHOUSE_TYPE_ID | long | 否 | - | 仓库分类ID，对应TBL_WMS_WAREHOUSE_TYPE.CID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_WMS_WAREHOUSE.CWAREHOUSE_TYPE_ID = TBL_WMS_WAREHOUSE_TYPE.CID
  - TBL_WMS_WAREHOUSE.CID = TBL_WMS_LOCATION.CWAREHOUSE_ID
  - TBL_WMS_WAREHOUSE.CID = TBL_WMS_LINE_RECORD.CWAREHOUSE_ID
  - TBL_WMS_WAREHOUSE.CID = TBL_WMS_MANTISSA_RECORD.CWAREHOUSE_ID
  - TBL_WMS_WAREHOUSE.CID = TBL_SRM_RECEIVING_DTL.CWAREHOUSE_ID

---

#### 142 仓库类型 ( TBL_WMS_WAREHOUSE_TYPE )
- **业务含义**：包含了仓库类型信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CWAREHOUSE_TYPE_CODE | string | 是 | - | 仓库类型编码 |
| CWAREHOUSE_TYPE_NAME | string | 是 | - | 仓库类型名称 |
| CID | long | 否 | - | 主键 |
| CIS_BATCH_CTRL | string | 是 | - | 是否批号，Y：是；N：否 |
| CIS_CHECK | string | 是 | - | 是否检验，Y：是；N：否 |
| CIS_LOCATION_CTRL | string | 是 | - | 是否货位，Y：是；N：否 |
| CIS_PRINT | string | 是 | - | 是否打条码，Y：是；N：否 |
| CREMARK | string | 是 | - | 备注 |
| CSOURCE_ID | string | 是 | - | 来源ID |
| CWAREHOUSE_TYPE_CODE | string | 是 | - | 类别代码 |
| CWAREHOUSE_TYPE_NAME | string | 是 | - | 类别名称 |
| CWAREHOUSE_TYPE_PROPERTY | string | 是 | - | 仓库属性 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_WMS_WAREHOUSE_TYPE.CID = TBL_WMS_WAREHOUSE.CWAREHOUSE_TYPE_ID

---

#### 143 仓库区域 ( TBL_WMS_AREA )
- **业务含义**：包含了仓库所属区域的信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CAREA_CODE | string | 是 | - | 区域代码 |
| CAREA_DESC | string | 是 | - | 区域描述 |
| CAREA_NAME | string | 是 | - | 区域名称 |
| CPERSON_ID | string | 是 | - | 区域管理员ID，对应TBL_SYS_USER.CID |
| CREMARK | string | 是 | - | 备注 |
| CSOURCE_ID | string | 是 | - | 来源ID |
| CWAREHOUSE_ID | long? | 是 | - | 仓库ID，对应TBL_WMS_WAREHOUSE.CID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_WMS_AREA.CWAREHOUSE_ID = TBL_WMS_WAREHOUSE.CID
  - TBL_WMS_AREA.CPERSON_ID = TBL_SYS_USER.CID

---

#### 144 条码拆分记录表 ( TBL_WMS_BARCODE_SPLIT_RECORD )
- **业务含义**：记录了物料条码的拆分记录信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CREMARK | string | 是 | - | 备注 |
| CSOURCE_BARCODE_ID | long? | 是 | - | 来源条码ID，对应TBL_WMS_ITEM_BARCODE.CID |
| CSPLIT_QTY | decimal? | 是 | - | 拆分数量 |
| CSPLIT_TIME | DateTime? | 是 | - | 拆分时间 |
| CSPLIT_USER | string | 是 | - | 拆分人，对应TBL_SYS_USER.CUSER_NAME |
| CTARGET_BARCODE_ID | long? | 是 | - | 目标条码ID，对应TBL_WMS_ITEM_BARCODE.CID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_WMS_BARCODE_SPLIT_RECORD.CSOURCE_BARCODE_ID = TBL_WMS_ITEM_BARCODE.CID
  - TBL_WMS_BARCODE_SPLIT_RECORD.CTARGET_BARCODE_ID = TBL_WMS_ITEM_BARCODE.CID
  - TBL_WMS_BARCODE_SPLIT_RECORD.CSPLIT_USER = TBL_SYS_USER.CUSER_NAME

---

#### 145 仓库物料标签打印日志表 ( TBL_WMS_PRINT_LOG )
- **业务含义**：记录了仓库根据库存打印的物料条码的日志信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| lotcode | string | 是 | - | 批次号 |
| materialcode | string | 是 | - | 物料编码，对应TBL_BD_ITEM.CITEM_NO |
| materialname | string | 是 | - | 物料名称 |
| order | string | 是 | - | 单据号 |
| printer | string | 是 | - | 打印机名称 |
| qty | int | 否 | - | 打印数量 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：无

---

#### 146 ERP库存与打印条码关联表 ( TBL_WMS_STOCK_BARCODE_LINK )
- **业务含义**：记录ERP库存物料与打印的物料条码的关联关系
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CBARCODE_ID | long | 否 | - | 打印条码记录ID，对应TBL_WMS_ITEM_BARCODE.CID |
| CREMARK | string | 是 | - | 备注 |
| CSTOCK_ID | long | 否 | - | ERP库存记录ID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_WMS_STOCK_BARCODE_LINK.CBARCODE_ID = TBL_WMS_ITEM_BARCODE.CID

---

#### 147 ERP成品库存视图 ( VM_ERP_FGI )
- **业务含义**：包含了ERP系统中的产品的成品实时库存信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| AgeStock | int | 否 | - | 库龄 |
| BatchNumber | string | 是 | - | 批次号 |
| Currency | string | 是 | - | 原币 |
| CustMatCode | string | 是 | - | 客户物料编码 |
| CustomerCode | string | 是 | - | 客户代码 |
| CustomerName | string | 是 | - | 客户名称 |
| DateCode | string | 是 | - | 周期码 |
| IfConsigment | bool | 否 | - | 是否寄售 |
| InventoryArea_Sqft | decimal | 否 | - | 库存面积ft2 |
| InventoryArea_Sqm | decimal | 否 | - | 库存面积m2 |
| JobId | string | 是 | - | 工单ID |
| LocalCurrency | string | 是 | - | 本币 |
| PartId | string | 是 | - | PartId |
| PartName | string | 是 | - | 客户型号 |
| PartNum | string | 是 | - | 产品料号，对应TBL_BD_ITEM.CITEM_NO |
| PartRev | string | 是 | - | 版本 |
| PcsArea_Sqm | decimal | 否 | - | 单PCS面积m2 |
| PcsOfArray | decimal | 否 | - | PCS/SET |
| ProductGroupName | string | 是 | - | 产品分组 |
| QtyOfArray | decimal? | 是 | - | 库存交货板数 |
| QtyOfUnit | decimal? | 是 | - | 库存单元数 |
| Rack | string | 是 | - | 货位 |
| ShelfLife | int | 否 | - | 保质期 |
| SOAmountNoTax | decimal | 否 | - | 原币销售未税金额 |
| SOAmountWithTax | decimal | 否 | - | 原币销售含税金额 |
| SOLocalAmountNoTax | decimal | 否 | - | 本币销售未税金额 |
| SOLocalAmountWithTax | decimal | 否 | - | 本币销售含税金额 |
| SOLocalPriceNoTax | decimal | 否 | - | 本币销售未税单价 |
| SOLocalPriceWithTax | decimal | 否 | - | 本币销售含税单价 |
| SOPriceNoTax | decimal | 否 | - | 原币销售未税单价 |
| SOPriceWithTax | decimal | 否 | - | 原币销售含税单价 |
| StockDate | DateTime | 否 | - | 入库日期 |
| StockType | string | 是 | - | 入库类型 |
| WarehouseCode | string | 是 | - | 仓库代码 |
| WarehouseName | string | 是 | - | 仓库名称 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：无

---

#### 148 ERP成品入库记录 ( VM_ERP_FGI_IN )
- **业务含义**：包含了ERP系统中的产品的成品入库记录信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| BatchNumber | string | 是 | - | 批次号 |
| Company | string | 是 | - | 公司名称 |
| ContractItemId | int? | 是 | - | 合同项ID |
| ContractSOId | int? | 是 | - | 合同销售订单ID |
| CostAmout | decimal? | 是 | - | 本币不含税金额 |
| CostPrice | decimal? | 是 | - | 本币不含税单价 |
| CreateDate | DateTime? | 是 | - | 创建日期 |
| Creator | string | 是 | - | 建单人员 |
| Culayers | int? | 是 | - | 铜层数 |
| Currency | string | 是 | - | 货币 |
| CustomerCode | string | 是 | - | 客户代码 |
| CustomerName | string | 是 | - | 客户名称 |
| DateCode | string | 是 | - | 周期码 |
| EnterDate | DateTime? | 是 | - | 实际入仓日期 |
| JobId | int? | 是 | - | 生产任务ID |
| LocalCurrency | string | 是 | - | 本位币 |
| LocationName | string | 是 | - | 储区名称 |
| MfgDate | DateTime? | 是 | - | 制造日期 |
| PartName | string | 是 | - | 客户型号 |
| PartNum | string | 是 | - | 产品料号，对应TBL_BD_ITEM.CITEM_NO |
| PartRev | string | 是 | - | 版本 |
| PcsArea_Sqft | decimal? | 是 | - | 单PCS面积ft2 |
| PcsArea_Sqm | decimal? | 是 | - | 单PCS面积m2 |
| PcsOfArray | decimal? | 是 | - | PCS/SET |
| Plants | string | 是 | - | 工厂名称 |
| PlantsId | int? | 是 | - | 工厂ID |
| POItemId | int? | 是 | - | 采购订单项ID |
| ProductGroupName | string | 是 | - | 产品分组 |
| QtyOfArray | decimal? | 是 | - | 入仓数量SET |
| QtyOfPCS | decimal? | 是 | - | 入仓数量PCS |
| SalesPartType | string | 是 | - | 销售部件类型 |
| Stauts | string | 是 | - | 单据状态（Stocked：已入库；Active：未入仓） |
| StockArea_Sqft | decimal? | 是 | - | 入仓面积ft2 |
| StockArea_Sqm | decimal | 否 | - | 入仓面积m2 |
| StockCode | string | 是 | - | 入仓单号 |
| StockDate | DateTime? | 是 | - | 入仓日期 |
| StockFormId | int? | 是 | - | 入库表单ID |
| StockFormItemId | int? | 是 | - | 入库表单项ID |
| StockItemNote | string | 是 | - | 明细备注 |
| StockNote | string | 是 | - | 入仓备注 |
| StockType | string | 是 | - | 入仓类型(Production：生产入仓；Direct：直接入仓；Return：退货入仓；Outsource：外包入仓） |
| SupplierCode | string | 是 | - | 供应商代码 |
| SupplierName | string | 是 | - | 供应商名称 |
| WarehouseName | string | 是 | - | 仓库名称 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：无

---

#### 149 ERP成品出库记录 ( VM_ERP_FGI_OUT )
- **业务含义**：包含了ERP系统中的产品的成品出库记录信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| AllowOver | bool? | 是 | - | 允许SO数量超出 |
| AssignedArea_Sqft | double? | 是 | - | 订单实际出数面积ft2 |
| AssignedArea_Sqm | double | 否 | - | 订单实际出数面积m2 |
| AssignUser | string | 是 | - | 库存指派人员 |
| BusinessMan | string | 是 | - | 业务员 |
| Company | string | 是 | - | 公司名称 |
| CompanyAddress | string | 是 | - | 公司地址 |
| CompanyEname | string | 是 | - | 公司英文名称 |
| CompanyNote | string | 是 | - | 公司备注 |
| ConfirmedDate | DateTime? | 是 | - | 出库日期 |
| ConfirmedUser | string | 是 | - | 出库人员 |
| ConfirmTime | DateTime? | 是 | - | 回签日期 |
| ContactEmail | string | 是 | - | 联系人邮件 |
| ContactPhone | string | 是 | - | 联系人电话 |
| ContractItemId | int? | 是 | - | ContractItemId |
| Creator | string | 是 | - | 制单人员 |
| Culayers | int? | 是 | - | 层 |
| Currency | string | 是 | - | 货币 |
| CurrencyId | int? | 是 | - | CurrencyId |
| Cust_Ref | string | 是 | - | 外部参考号 |
| CustContractNO | string | 是 | - | 客户合同号 |
| CustMatCode | string | 是 | - | 客户物料代码 |
| CustomerCode | string | 是 | - | 客户代码 |
| CustomerName | string | 是 | - | 客户名称 |
| CustomerNickName | string | 是 | - | 客户昵称 |
| CustOrderNumber | string | 是 | - | 客户订单号 |
| EndCustomer | string | 是 | - | 终端客户 |
| ExchangeRate | decimal? | 是 | - | 汇率 |
| FreeAssignedArea_Sqft | double? | 是 | - | 赠品实际出数面积ft2 |
| FreeAssignedArea_Sqm | double? | 是 | - | 赠品实际出数面积m2 |
| GrossWeight | decimal? | 是 | - | 毛重 |
| Ifassign | bool? | 是 | - | 是否已经出库 |
| IfOsOrder | bool? | 是 | - | 是否外协 |
| InNote | string | 是 | - | 内部备注 |
| Internal_Ref | string | 是 | - | 内部参考号 |
| ItemNote | string | 是 | - | 明细备注 |
| JobId | int? | 是 | - | jobId |
| LinkMan | string | 是 | - | 联系人 |
| LocalCurrency | string | 是 | - | 本币 |
| NetWeight | decimal? | 是 | - | 净重 |
| Packing_Numer | string | 是 | - | 送货单号 |
| PackingSlipId | int? | 是 | - | PackingSlipId |
| PanelType | string | 是 | - | 板类型 |
| PartName | string | 是 | - | 客户型号 |
| PartNum | string | 是 | - | 产品料号，对应TBL_BD_ITEM.CITEM_NO |
| PartType | string | 是 | - | 产品类型 |
| PcsOfArray | int? | 是 | - | PCS/SET |
| PlantId | int? | 是 | - | plantId |
| ProductGroup | string | 是 | - | 产品组别 |
| ProductGroupCode | string | 是 | - | 产品分组代码 |
| ProductGroupName | string | 是 | - | 产品分组名称 |
| QtyFreeAssigned | int? | 是 | - | 赠品实际出数PCS |
| QtyofArrayAssigned | int? | 是 | - | 订单实际出数SET |
| QtyOfCartons | int? | 是 | - | 箱数 |
| QtyofPCSAssigned | int? | 是 | - | 订单实际出数PCS |
| QtyofShipArray | int? | 是 | - | 订单计划出数SET |
| QtyofShipFree | int? | 是 | - | 赠品计划出数PCS |
| QtyofShipOrdered | int? | 是 | - | 订单计划出数PCS |
| SalesPartName | string | 是 | - | 客户型号 |
| SalesPartNum | string | 是 | - | 本厂型号 |
| ShipingNotes_Numer | string | 是 | - | 出库单号 |
| ShippedDate | DateTime? | 是 | - | 装运日期 |
| ShippingAddress | string | 是 | - | 送货地址 |
| ShippingCharge | decimal? | 是 | - | 参考运费 |
| ShippingMethod | string | 是 | - | 运输方式 |
| ShippingNote | string | 是 | - | 运号单备注 |
| ShipPlanDate | DateTime? | 是 | - | 计划出货日期 |
| ShipType | string | 是 | - | 出货类型 ForDomestic：内销；ForExport：外销 |
| ShipUnit | string | 是 | - | 出货单位名称 |
| ShipUser | string | 是 | - | 装运人员 |
| SO_Notes | string | 是 | - | 分析代码1 |
| SOAmountNoTax | decimal? | 是 | - | 原币不含税出货金额 |
| SOAmountWithTax | decimal? | 是 | - | 原币含税出货金额 |
| SOLocalAmountNoTax | decimal? | 是 | - | 本币不含税出货金额 |
| SOLocalAmountWithTax | decimal? | 是 | - | 本币含税出货金额 |
| SOLocalPriceNoTax | decimal? | 是 | - | 本币不含税单价 |
| SOLocalPriceWithTax | decimal? | 是 | - | 本币含税单价 |
| SONumber | string | 是 | - | 销售订单号 |
| SOPriceNoTax | decimal? | 是 | - | 原币不含税单价 |
| SOPriceWithTax | decimal? | 是 | - | 原币含税单价 |
| Status | int? | 是 | - | 状态 |
| TaxRate | decimal? | 是 | - | 税率 |
| Type | string | 是 | - | 类型 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：无

---

#### 150 IQC检验退货记录 ( VM_ERP_IQC_RETURN )
- **业务含义**：包含了ERP系统中对物料进行IQC检验后不合格的物料退货记录
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CBATCH_CODE | string | 是 | - | 批次号 |
| CCATEGORY_NAME | string | 是 | - | 物料分组 |
| CCHECK_NO | string | 是 | - | 检验单号 |
| CCHECK_USER | string | 是 | - | 检验人员 |
| CDEFECTED_QTY | decimal? | 是 | - | 不良数量 |
| CDELIVERY_CODE | string | 是 | - | 送货单号 |
| CINSPECTED_QTY | decimal? | 是 | - | 检验数量 |
| CLOCATION_NAME | string | 是 | - | 货位名称 |
| CMATERIAL_CODE | string | 是 | - | 物料编码，对应TBL_BD_ITEM.CITEM_NO |
| CMATERIAL_NAME | string | 是 | - | 物料名称 |
| CMATERIAL_STANDARD | string | 是 | - | 物料规格 |
| CQUALIFIED_QTY | decimal? | 是 | - | 合格数量 |
| CRECEIVE_DATE | DateTime? | 是 | - | 收货日期 |
| CRETURN_QTY | decimal? | 是 | - | 待退货数量 |
| CRETURNED_QTY | decimal? | 是 | - | 已退货数量 |
| CSCRAPPED_QTY | decimal? | 是 | - | 报废数量 |
| CSTATUS | string | 是 | - | 状态 |
| CSUPPLIER_NAME | string | 是 | - | 供应商名称 |
| CTEST_DATE | DateTime? | 是 | - | 检验日期 |
| CTYPE | string | 是 | - | 类型 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - VM_ERP_IQC_RETURN.CMATERIAL_CODE = TBL_BD_ITEM.CITEM_NO

---

#### 151 物料出入库记录 ( VM_ERP_MATERIAL_OUT_IN )
- **业务含义**：包含了ERP系统中所有物料的从仓库的出库和入库的记录
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| 标准规格 | string | 是 | - | 标准规格 |
| 部门 | string | 是 | - | 部门 |
| 仓库 | string | 是 | - | 仓库 |
| 单据大类 | string | 是 | - | 单据大类 |
| 单据号码 | string | 是 | - | 单据号码 |
| 单据小类 | string | 是 | - | 单据小类 |
| 工序 | string | 是 | - | 工序，对应TBL_BD_PROCESS.CPROCESS_NAME |
| 工艺 | string | 是 | - | 工艺 |
| 供应商 | string | 是 | - | 供应商 |
| 供应商批号 | string | 是 | - | 供应商批号 |
| 库存单位 | string | 是 | - | 库存单位 |
| 录入日期 | DateTime? | 是 | - | 录入日期 |
| 是否寄售 | string | 是 | - | 是否寄售 |
| 数量 | decimal? | 是 | - | 数量 |
| 物料代码 | string | 是 | - | 物料代码，对应TBL_BD_ITEM.CITEM_NO |
| 物料分组 | string | 是 | - | 物料分组 |
| 物料名称 | string | 是 | - | 物料名称 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：无

---

#### 152 ERP退料记录明细 ( VM_ERP_MATERIAL_RETURN_ITEM )
- **业务含义**：包含ERP系统中的物料退料到仓库的记录
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CBUY_UNIT | string | 是 | - | 采购单位 |
| CCATEGORY_NAME | string | 是 | - | 类别名称 |
| CCONSIGNMENT_FLAG | string | 是 | - | 寄售标志 |
| CDATETIME_CREATED | DateTime? | 是 | - | 创建日期时间 |
| CENTER_DATE | DateTime? | 是 | - | 实际退料日期 |
| CINTERNAL_BATCHNO | string | 是 | - | 内部批号 |
| CISSUE_DATE | DateTime? | 是 | - | 物料发放日期 |
| CMATERIAL_CODE | string | 是 | - | 物料编码，对应TBL_BD_ITEM.CITEM_NO |
| CMATERIAL_NAME | string | 是 | - | 物料名称 |
| CMATERIAL_STANDARD | string | 是 | - | 物料规格 |
| CMATERIAL_TYPE | string | 是 | - | 物料类型 |
| CPOST_ROLE | string | 是 | - | 岗位角色 |
| CPROCESS | string | 是 | - | 工序，对应TBL_BD_PROCESS.CPROCESS_NAME |
| CRETURN_CODE | string | 是 | - | 退料单号 |
| CRETURN_DATE | DateTime? | 是 | - | 退料日期 |
| CRETURN_DEPARTMENT | string | 是 | - | 退料部门 |
| CRETURN_PEOPLE | string | 是 | - | 退料人员 |
| CRETURNED_QTY | decimal? | 是 | - | 已退料数量 |
| CSTEPS | string | 是 | - | 步骤 |
| CSTOCK_BUY_RATE | decimal? | 是 | - | 库存采购比率 |
| CSTOCK_UNIT | string | 是 | - | 库存单位 |
| CSUPPLIERS_CODE | string | 是 | - | 供应商编码 |
| CSUPPLIERS_NAME | string | 是 | - | 供应商名称 |
| CTYPE | string | 是 | - | 类型 |
| CUSER_CREATED | string | 是 | - | 创建人 |
| CWAREHOUSE | string | 是 | - | 仓库 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - VM_ERP_MATERIAL_RETURN_ITEM.CMATERIAL_CODE = TBL_BD_ITEM.CITEM_NO
  - VM_ERP_MATERIAL_RETURN_ITEM.CPROCESS = TBL_BD_PROCESS.CPROCESS_NAME

---

#### 153 ERP退料申请明细 ( VM_ERP_MATERIAL_RETURN_REQUEST_ITEM )
- **业务含义**：包含ERP系统中的物料退料到仓库的申请明细记录
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CAPPROVE_STATUS | string | 是 | - | 审批状态 |
| CCATEGORY_NAME | string | 是 | - | 物料类别名称 |
| CCOMPANY | string | 是 | - | 公司名称 |
| CDEPARTMENT | string | 是 | - | 部门 |
| CITEM_NOTE | string | 是 | - | 物料项备注 |
| CMATERIAL_CODE | string | 是 | - | 物料编码，对应TBL_BD_ITEM.CITEM_NO |
| CMATERIAL_NAME | string | 是 | - | 物料名称 |
| CMATERIAL_STANDARD | string | 是 | - | 物料规格/标准 |
| CMATERIALS_ISSUE_CODE | string | 是 | - | 物料发放单号 |
| CORDER_STATUS | string | 是 | - | 订单状态 |
| CPLANTS | string | 是 | - | 工厂/车间 |
| CPOST_ROLE | string | 是 | - | 岗位角色 |
| CPROCESS | string | 是 | - | 工序，对应TBL_BD_PROCESS.CPROCESS_NAME |
| CQUANTITY | decimal? | 是 | - | 申请退料数量 |
| CREMARK | string | 是 | - | 备注说明 |
| CRETURN_CODE | string | 是 | - | 退料单号 |
| CRETURN_DATE | DateTime? | 是 | - | 退料日期 |
| CRETURNED_QTY | decimal? | 是 | - | 已退料数量 |
| CSTEPS | string | 是 | - | 生产步骤 |
| CSTOCK_UNIT | string | 是 | - | 库存单位 |
| CTO_RETURNED | string | 是 | - | 待退料标志（0/1） |
| CTO_RETURNED_QTY | decimal? | 是 | - | 待退料数量 |
| CTYPE | string | 是 | - | 退料类型 |
| CUSER_CREATED | string | 是 | - | 创建人 |
| CWAREHOUSE | string | 是 | - | 仓库 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - VM_ERP_MATERIAL_RETURN_REQUEST_ITEM.CMATERIAL_CODE = TBL_BD_ITEM.CITEM_NO
  - VM_ERP_MATERIAL_RETURN_REQUEST_ITEM.CPROCESS = TBL_BD_PROCESS.CPROCESS_NAME

---

#### 154 ERP退货明细 ( VM_ERP_RETURN_GI )
- **业务含义**：包含客户退货的信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CARDate | DateTime? | 是 | - | CAR日期（纠正措施报告日期） |
| CARReport | string | 是 | - | CAR报告（纠正措施报告） |
| Company | string | 是 | - | 公司名称 |
| CompanyId | int? | 是 | - | 公司ID |
| ComplainmentId | int? | 是 | - | 投诉ID |
| ComplainmentType | string | 是 | - | 投诉类型 |
| ComplaintContent | string | 是 | - | 投诉内容 |
| ComplaintDate | DateTime? | 是 | - | 投诉日期 |
| ComplaintMail | string | 是 | - | 投诉邮箱 |
| ComplaintMan | string | 是 | - | 投诉负责人 |
| ComplaintNumber | string | 是 | - | 投诉编号 |
| ComplaintTel | string | 是 | - | 投诉电话 |
| ComplaintType | string | 是 | - | 投诉类型 |
| ContractItemId | int? | 是 | - | 合同项ID |
| Creator | string | 是 | - | 创建人 |
| Currency | string | 是 | - | 币种 |
| CustomerCode | string | 是 | - | 客户代码 |
| CustomerName | string | 是 | - | 客户名称 |
| DebitMemoAmount | decimal? | 是 | - | 借项凭单金额 |
| EnterDate | DateTime? | 是 | - | 录入日期 |
| NewSONumber | string | 是 | - | 新销售订单号 |
| OrderStatus | string | 是 | - | 订单状态 |
| OrderUnit | string | 是 | - | 订购单位 |
| PackingSlipItemId | int? | 是 | - | 装箱单行ID |
| PackingSlipItemNumber | string | 是 | - | 装箱单行号 |
| PartArea | decimal | 否 | - | 部件区域 |
| PartName | string | 是 | - | 部件名称 |
| PartNum | string | 是 | - | 部件编号，对应TBL_BD_ITEM.CITEM_NO |
| PcsArea_Sqm | decimal | 否 | - | 件数区域/面积（平方米） |
| Price | decimal? | 是 | - | 价格 |
| QtyArrayReturn | decimal? | 是 | - | 阵列退货数量 |
| QtyPCSReturn | decimal? | 是 | - | 件数退货数量 |
| QtyReceived | decimal? | 是 | - | 已接收数量 |
| RefNumber | string | 是 | - | 参考编号 |
| ReturnAmount | decimal? | 是 | - | 退货金额 |
| SalesPartName | string | 是 | - | 销售部件名称 |
| SalesPartNum | string | 是 | - | 销售部件编号 |
| SONumber | string | 是 | - | 销售订单号 |
| ToReceive | decimal? | 是 | - | 待接收数量 |
| Type | string | 是 | - | 类型 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：无

---

#### 155 ERP库存物料视图 ( VM_ERP_STOCK_INFO )
- **业务含义**：包含了ERP系统中的物料实时库存信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CID | long | 否 | - | 记录ID |
| CINTERNAL_BATCH_NO | string | 是 | - | 内部批号 |
| CMATERIAL_CODE | string | 是 | - | 物料编码，对应TBL_BD_ITEM.CITEM_NO |
| CMATERIAL_NAME | string | 是 | - | 物料名称 |
| CMATERIAL_STANDARD | string | 是 | - | 物料规格 |
| CPO_CODE | string | 是 | - | 采购单号 |
| CQTY_ON_HAND | decimal? | 是 | - | 在库数量 |
| CSTOCK_DATE | DateTime | 否 | - | 库存日期 |
| CSUPP_BATCH_NO | string | 是 | - | 供应商批号 |
| CSUPPLIER_NAME | string | 是 | - | 供应商名称 |
| CWAREHOUSE_NAME | string | 是 | - | 仓库名称 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - VM_ERP_STOCK_INFO.CMATERIAL_CODE = TBL_BD_ITEM.CITEM_NO

---

### 2.10 供应链协同

> 本章节数据来源于 Excel 工作表：`供应链协同`

#### 156 采购单 ( TBL_SRM_PO )
- **业务含义**：包含从ERP系统同步到MES系统的采购单信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CBUSINESS_TYPE | string | 是 | - | 业务类型 |
| CCHANGE_DATETIME | DateTime? | 是 | - | 变更时间 |
| CPERSON_ID | string | 是 | - | 采购员ID |
| CPO | string | 是 | - | 采购单号 |
| CPURCHASE_DATE | DateTime? | 是 | - | 采购日期 |
| CPURCHASE_TYPE | string | 是 | - | 采购方式 |
| CREMARK | string | 是 | - | 备注 |
| CREVIEW_DATETIME | DateTime? | 是 | - | 审核时间 |
| CSOURCE_ID | string | 是 | - | 来源ID |
| CSTATUS | string | 是 | - | 状态 |
| CSUPPLIER_ID | Int64? | 是 | - | 供应商ID，对应TBL_BD_SUPPLIER.CID |
| CID | long | 否 | - | 主键 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_SRM_PO.CSUPPLIER_ID = TBL_BD_SUPPLIER.CID
  - TBL_SRM_PO.CID = TBL_SRM_PO_DETAIL.CPO_ID

---

#### 157 采购订单交付表 ( TBL_SRM_PO_DELIVERY )
- **业务含义**：包含已交付的采购单信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CASSIGNED_QTY | decimal? | 是 | - | 分配数量 |
| CBATCH_CODE | string | 是 | - | 批号 |
| CDELIVERED_QTY | decimal? | 是 | - | 送货数量 |
| CGENERATE_BARCODE_QTY | decimal? | 是 | - | 已打条码数量 |
| CIN_STOCK_QTY | decimal? | 是 | - | 入库数量 |
| CITEM_CODE | string | 是 | - | 物料编码 |
| CITEM_ID | Int64? | 是 | - | 外键，物料ID  对应TBL_BD_ITEM.CID |
| CITEM_NAME | string | 是 | - | 物料名称 |
| CITEM_SPEC | string | 是 | - | 物料规格 |
| CPO_DETAIL_ID | Int64? | 是 | - | 采购订单明细ID，对应TBL_SRM_PO_DETAIL.CID |
| CQTY | decimal? | 是 | - | 数量 |
| CREMARK | string | 是 | - | 备注 |
| CRETURN_QTY | decimal? | 是 | - | 退货数量 |
| CSOURCE_ID | string | 是 | - | 来源ID |
| CSTATUS | string | 是 | - | 状态 |
| CSUPPLIER_CONFIRM_DELIVERY_DATE | DateTime? | 是 | - | 供应商回复交期 |
| CSUPPLIER_CONFIRM_REMARK | string | 是 | - | 供应商备注 |
| CUNIT | string | 是 | - | 单位 |
| CID | long | 否 | - | 主键 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_SRM_PO_DELIVERY.CITEM_ID = TBL_BD_ITEM.CID
  - TBL_SRM_PO_DELIVERY.CPO_DETAIL_ID = TBL_SRM_PO_DETAIL.CID
  - TBL_SRM_PO_DELIVERY.CID = TBL_WMS_ITEM_BARCODE.CSRC_ID
  - TBL_SRM_PO_DELIVERY.CID = TBL_SRM_RECEIVING_DTL.CPO_DELIVERY_ID

---

#### 158 采购订单明细 ( TBL_SRM_PO_DETAIL )
- **业务含义**：包含从ERP系统同步到MES系统的采购单明细信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CASSIGNED_QTY | decimal? | 是 | - | 分配数量 |
| CBUSINESS_BILL_CODE | string | 是 | - | 业务单号 |
| CCHANGE_DATETIME | DateTime? | 是 | - | 变更时间 |
| CDELIVERED_QTY | decimal? | 是 | - | 已交货数量 |
| CDELIVERY_DATETIME | DateTime? | 是 | - | 交货日期 |
| CGENERATE_BARCODE_QTY | decimal? | 是 | - | 已打条码数量 |
| CIN_STOCK_QTY | decimal? | 是 | - | 入库数量 |
| CITEM_CODE | string | 是 | - | 物料编码 |
| CITEM_ID | Int64? | 是 | - | 外键，物料ID  对应TBL_BD_ITEM.CID |
| CITEM_NAME | string | 是 | - | 物料名称 |
| CITEM_SPEC | string | 是 | - | 物料规格 |
| CORIGIN_TYPE | string | 是 | - | 来源类型 |
| CPO_ID | Int64? | 是 | - | 采购订单ID，对应TBL_SRM_PO.CID |
| CQTY | decimal? | 是 | - | 订单数量 |
| CREMARK | string | 是 | - | 备注 |
| CRETURN_QTY | decimal? | 是 | - | 退货数量 |
| CSEQ | int? | 是 | - | 订单行号 |
| CSOURCE_ID | string | 是 | - | 来源ID |
| CUNIT | string | 是 | - | 单位 |
| CID | long | 否 | - | 主键 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_SRM_PO_DETAIL.CITEM_ID = TBL_BD_ITEM.CID
  - TBL_SRM_PO_DETAIL.CPO_ID = TBL_SRM_PO.CID
  - TBL_SRM_PO_DETAIL.CID = TBL_SRM_PO_DELIVERY.CPO_DETAIL_ID
  - TBL_SRM_PO_DETAIL.CID = TBL_SRM_RECEIVING_DTL.CPO_DETAIL_ID

---

#### 159 收货单主表 ( TBL_SRM_RECEIVING )
- **业务含义**：包含从ERP系统同步到MES系统的收货单信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CBATCH_CODE | string | 是 | - | 批号 |
| CBILL_TYPE | string | 是 | - | 单据类型 |
| CBUSINESS_TYPE | string | 是 | - | 业务类型 |
| CPURCHASE_TYPE | string | 是 | - | 采购类型 |
| CRECEIVING_CUSTOMER | string | 是 | - | 收货客户名称 |
| CRECEIVING_DATE | DateTime? | 是 | - | 收货日期 |
| CRECEIVING_DEPT | string | 是 | - | 收货部门 |
| CRECEIVING_NO | string | 是 | - | 收货单号 |
| CRECEIVING_USER | string | 是 | - | 收货人，对应TBL_SYS_USER.CUSER_NAME |
| CREMARK | string | 是 | - | 备注 |
| CSOURCE_ID | string | 是 | - | 来源ID |
| CSTATUS | string | 是 | - | 状态；BARCODE_STORAGE：已收货；BARCODE_DELIVERY：运输中；BARCODE_STOCK：已入库 |
| CSUPPLIER_ID | Int64? | 是 | - | 供应商ID，对应TBL_BD_SUPPLIER.CID |
| CID | long | 否 | - | 主键 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_SRM_RECEIVING.CSUPPLIER_ID = TBL_BD_SUPPLIER.CID
  - TBL_SRM_RECEIVING.CRECEIVING_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_SRM_RECEIVING.CID = TBL_SRM_RECEIVING_DTL.CRECEIVING_ID

---

#### 160 收货单条码关联表 ( TBL_SRM_RECEIVING_BARCODE )
- **业务含义**：包含收获单明细与对应物料条码的关联信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CBARCODE | string | 是 | - | 条码，对应TBL_WMS_ITEM_BARCODE.CBARCODE |
| CRECEIVING_DTL_ID | Int64? | 是 | - | 收货单明细ID，对应TBL_SRM_RECEIVING_DTL.CID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_SRM_RECEIVING_BARCODE.CBARCODE = TBL_WMS_ITEM_BARCODE.CBARCODE
  - TBL_SRM_RECEIVING_BARCODE.CRECEIVING_DTL_ID = TBL_SRM_RECEIVING_DTL.CID

---

#### 161 收货单明细表 ( TBL_SRM_RECEIVING_DTL )
- **业务含义**：包含从ERP系统同步到MES系统的收货单明细信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CBATCH_CODE | string | 是 | - | 批号 |
| CDELIVER_QTY | decimal? | 是 | - | 供应商送货数量 |
| CEMERGENCY_LEVEL | int? | 是 | - | 来料检验紧急程度 |
| CGOOD_QTY | decimal? | 是 | - | 合格数量 |
| CINSOTCK_QTY | decimal? | 是 | - | 入库数量 |
| CINSPECT_DATETIME | DateTime? | 是 | - | 检验时间 |
| CINSPECT_RESULT | string | 是 | - | 检验结果 |
| CINSPECT_USER | string | 是 | - | 检验人，对应TBL_SYS_USER.CUSER_NAME |
| CINSTOCK_DATETIME | DateTime? | 是 | - | 入库时间 |
| CITEM_CODE | string | 是 | - | 物料编码 |
| CITEM_ID | Int64? | 是 | - | 外键，物料ID  对应TBL_BD_ITEM.CID |
| CITEM_NAME | string | 是 | - | 物料名称 |
| CITEM_SPEC | string | 是 | - | 物料规格 |
| CLOCATION_ID | Int64? | 是 | - | 货位ID，对应TBL_WMS_LOCATION.CID |
| CNG_QTY | decimal? | 是 | - | 不合格数量 |
| CPO | string | 是 | - | 采购单号 |
| CPO_DELIVERY_ID | long? | 是 | - | 采购单交付ID，对应TBL_SRM_PO_DELIVERY.CID |
| CPO_DETAIL_ID | long? | 是 | - | 采购单明细ID，对应TBL_SRM_PO.CID |
| CPO_QTY | decimal? | 是 | - | 采购数量 |
| CPO_SEQ | int? | 是 | - | 采购订单行号 |
| CRECEIVING_ID | Int64? | 是 | - | 收货单ID，对应TBL_SRM_RECEIVING.CID |
| CRECEIVING_QTY | decimal? | 是 | - | 收货数量 |
| CRETURN_QTY | decimal? | 是 | - | 退货数量 |
| CSEQ | int? | 是 | - | 收货单行号 |
| CSO | string | 是 | - | 销售单号 |
| CSOURCE_ID | string | 是 | - | 来源ID |
| CSOURCE_NO | string | 是 | - | 来源单号 |
| CSOURCE_TYPE | string | 是 | - | 来源类型 |
| CSTATUS | string | 是 | - | 状态；BARCODE_STORAGE：已收货；BARCODE_DELIVERY：运输中；BARCODE_STOCK：已入库 |
| CUNIT | string | 是 | - | 单位 |
| CWAREHOUSE_ID | Int64? | 是 | - | 仓库ID，对应TBL_WMS_WAREHOUSE.CID |
| CID | long | 否 | - | 主键 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_SRM_RECEIVING_DTL.CITEM_ID = TBL_BD_ITEM.CID
  - TBL_SRM_RECEIVING_DTL.CLOCATION_ID = TBL_WMS_LOCATION.CID
  - TBL_SRM_RECEIVING_DTL.CWAREHOUSE_ID = TBL_WMS_WAREHOUSE.CID
  - TBL_SRM_RECEIVING_DTL.CPO_DELIVERY_ID = TBL_SRM_PO_DELIVERY.CID
  - TBL_SRM_RECEIVING_DTL.CPO_DETAIL_ID = TBL_SRM_PO_DETAIL.CID
  - TBL_SRM_RECEIVING_DTL.CRECEIVING_ID = TBL_SRM_RECEIVING.CID
  - TBL_SRM_RECEIVING_DTL.CINSPECT_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_SRM_RECEIVING_DTL.CID = TBL_SRM_RECEIVING_BARCODE.CRECEIVING_DTL_ID
  - TBL_SRM_RECEIVING_DTL.CPO_DETAIL_ID = TBL_SRM_PO.CID

---

### 2.11 物料防错

> 本章节数据来源于 Excel 工作表：`物料防错`

#### 162 供应商替代关联表 ( TBL_SHEET_LINK_PP )
- **业务含义**：描述了物料供应商之间的可替代关系
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CLINK_SUPPLIER_ID | long | 否 | - | 被关联的供应商ID，对应TBL_BD_SUPPLIER.CID |
| CREMARK | string | 是 | - | 备注 |
| CSUPPLIER_ID | long | 否 | - | 供应商ID，对应TBL_BD_SUPPLIER.CID |
| CSUPPLIER_NAME | string | 是 | - | 供应商名称 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_SHEET_LINK_PP.CSUPPLIER_ID = TBL_BD_SUPPLIER.CID
  - TBL_SHEET_LINK_PP.CLINK_SUPPLIER_ID = TBL_BD_SUPPLIER.CID

---

#### 163 MES领料记录 ( TBL_WMS_PICKING_LOG )
- **业务含义**：包含MES系统中的领料记录(与ERP领料记录不同)
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CPICKING_CODE | string | 是 | - | 领料单号 |
| CPICKING_QTY | decimal? | 是 | - | 领料数量 |
| CREMARK | string | 是 | - | 备注 |
| CUSER_NAME | string | 是 | - | 领料人，对应TBL_SYS_USER.CUSER_NAME |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_WMS_PICKING_LOG.CUSER_NAME = TBL_SYS_USER.CUSER_NAME
  - TBL_WMS_PICKING_LOG.CID = TBL_WMS_PICKING_LOG_DTL.CPICKING_ID

---

#### 164 领料记录明细 ( TBL_WMS_PICKING_LOG_DTL )
- **业务含义**：包含MES系统中的领料记录明细信息(与ERP领料记录不同)
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CBARCODE_ID | long? | 是 | - | 条码ID，对应TBL_WMS_ITEM_BARCODE.CID |
| CPICKING_ID | long? | 是 | - | 领料主表ID |
| CQTY | decimal? | 是 | - | 领料数量 |
| CREMARK | string | 是 | - | 备注 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_WMS_PICKING_LOG_DTL.CBARCODE_ID = TBL_WMS_ITEM_BARCODE.CID
  - TBL_WMS_PICKING_LOG_DTL.CPICKING_ID = TBL_WMS_PICKING_LOG.CID

---

#### 165 工单与条码生产关联表 ( TBL_MO_BARCODE_PROD_LINK )
- **业务含义**：包含工单与条码在工序生产时的关联绑定信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CBARCODE_ID | long? | 是 | - | 条码ID，对应TBL_WMS_ITEM_BARCODE.CID |
| CMO_ID | long? | 是 | - | 工单ID，对应TBL_MO.CID |
| CPROCESS_ID | long? | 是 | - | 工序ID，对应TBL_BD_PROCESS.CID |
| CREMARK | string | 是 | - | 备注 |
| CSUPPLIER_BARCODE | string? | 是 | - | 供应商条码 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_MO_BARCODE_PROD_LINK.CBARCODE_ID = TBL_WMS_ITEM_BARCODE.CID
  - TBL_MO_BARCODE_PROD_LINK.CMO_ID = TBL_MO.CID
  - TBL_MO_BARCODE_PROD_LINK.CPROCESS_ID = TBL_BD_PROCESS.CID

---

### 2.12 SPC

> 本章节数据来源于 Excel 工作表：`SPC`

#### 166 SPC管控特性主表 ( TBL_SPC_CONTROL_CHARACTERISTIC )
- **业务含义**：描述了各工序的SPC管控配置相关信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CCALCULATION_METHOD | string | 是 | - | 计算方法 |
| CCHART_TYPE | string | 是 | - | 控制图类型 |
| CCPK | double? | 是 | - | CPK |
| CCRITIAL_CONTROL | string | 是 | - | 是否关键控制项 |
| CDECIML_PLACES | int? | 是 | - | 小数位数 |
| CMEASURE_INSTRUMENT | string | 是 | - | 测量仪器 |
| CMEASURE_METHOD | string | 是 | - | 测量方法 |
| CMEASURE_REMARK | string | 是 | - | 测量备注 |
| CPROCESS_ID | long? | 是 | - | 工序ID，对应TBL_BD_PROCESS.CID |
| CREFRENCE_FILE | string | 是 | - | 参考文件 |
| CSAMPLE_COUNT | int? | 是 | - | 抽样数量 |
| CSAMPLING_FREQ | int? | 是 | - | 抽样频率 |
| CSAMPLING_REMARK | string | 是 | - | 抽样说明 |
| CSAMPLING_UNIT | string | 是 | - | 抽样频率单位 |
| CSPECIFICATION_LOW_LIMIT | string | 是 | - | 规格下限 |
| CSPECIFICATION_STANDARD | double? | 是 | - | 规格中心值 |
| CSPECIFICATION_UP_LIMIT | string | 是 | - | 规格上限 |
| CSTATUS | int | 否 | - | 发布状态（0未发布、1已发布） |
| CTYPE | string | 是 | - | 特性类型 |
| CUNIT | string | 是 | - | 单位 |
| CVARIABLE_CODE | string | 是 | - | 特性编码 |
| CVARIABLE_NAME | string | 是 | - | 特性名称 |
| CWC_ID | long? | 是 | - | 工作中心ID，对应TBL_BD_WC.CID |
| CID | long | 否 | - | 主键 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_SPC_CONTROL_CHARACTERISTIC.CPROCESS_ID = TBL_BD_PROCESS.CID
  - TBL_SPC_CONTROL_CHARACTERISTIC.CWC_ID = TBL_BD_WC.CID
  - TBL_SPC_CONTROL_CHARACTERISTIC.CID = TBL_SPC_CONTROL_CHARACTERISTIC_ITEM_LINK.CVARIABLE_ID
  - TBL_SPC_CONTROL_CHARACTERISTIC.CID = TBL_SPC_CONTROL_CHARACTERISTIC_LIMIT.CVARIABLE_ID
  - TBL_SPC_CONTROL_CHARACTERISTIC.CID = TBL_SPC_CONTROL_CHARACTERISTIC_RULE_LINK.CVARIABLE_ID
  - TBL_SPC_CONTROL_CHARACTERISTIC.CID = TBL_SPC_DATA_REAL.CVARIABLE_ID

---

#### 167 SPC管控特性与对象关联表 ( TBL_SPC_CONTROL_CHARACTERISTIC_ITEM_LINK )
- **业务含义**：描述SPC具体管控配置与产品料号关联关系
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CDATA_SOURCE | string | 是 | - | 数据来源 |
| CITEM_NO | string | 是 | - | 料号，对应TBL_BD_ITEM.CITEM_NO |
| CTEMP_NO | string | 是 | - | 模板编号 |
| CTYPE | string | 是 | - | 关联对象类型 |
| CVARIABLE_ID | long? | 是 | - | 管控特性ID，对应TBL_SPC_CONTROL_CHARACTERISTIC.CID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_SPC_CONTROL_CHARACTERISTIC_ITEM_LINK.CVARIABLE_ID = TBL_SPC_CONTROL_CHARACTERISTIC.CID
  - TBL_SPC_CONTROL_CHARACTERISTIC_ITEM_LINK.CITEM_NO = TBL_BD_ITEM.CITEM_NO

---

#### 168 SPC管控特性控制限配置表 ( TBL_SPC_CONTROL_CHARACTERISTIC_LIMIT )
- **业务含义**：描述了SPC管控配置相关控制限信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CCONTROL_METHOD | string | 是 | - | 管制方法 |
| CLCL_CONTROL_LOW_LIMIT | double? | 是 | - | 下控制图管制下限 |
| CLCL_CONTROL_MIDDLE | double? | 是 | - | 下控制图管制中线 |
| CLCL_CONTROL_UP_LIMIT | double? | 是 | - | 下控制图管制上限 |
| CUCL_CONTROL_LOW_LIMIT | double? | 是 | - | 上控制图管制下限 |
| CUCL_CONTROL_MIDDLE | double? | 是 | - | 上控制图管制中线 |
| CUCL_CONTROL_UP_LIMIT | double? | 是 | - | 上控制图管制上限 |
| CVARIABLE_ID | long? | 是 | - | 管控特性ID，对应TBL_SPC_CONTROL_CHARACTERISTIC.CID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_SPC_CONTROL_CHARACTERISTIC_LIMIT.CVARIABLE_ID = TBL_SPC_CONTROL_CHARACTERISTIC.CID

---

#### 169 SPC管控特性与判异规则关联表 ( TBL_SPC_CONTROL_CHARACTERISTIC_RULE_LINK )
- **业务含义**：描述SPC具体管控配置与判异规则的关联关系
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CCHART_TYPE | int? | 是 | - | 图类型（1上图、2下图） |
| CRULE_ID | long? | 是 | - | 规则ID，对应TBL_SPC_RULE_OF_DISSENT.CID |
| CVARIABLE_ID | long? | 是 | - | 管控特性ID，对应TBL_SPC_CONTROL_CHARACTERISTIC.CID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_SPC_CONTROL_CHARACTERISTIC_RULE_LINK.CVARIABLE_ID = TBL_SPC_CONTROL_CHARACTERISTIC.CID
  - TBL_SPC_CONTROL_CHARACTERISTIC_RULE_LINK.CRULE_ID = TBL_SPC_RULE_OF_DISSENT.CID

---

#### 170 SPC实时采样数据表 ( TBL_SPC_DATA_REAL )
- **业务含义**：包含了每个进行SPC管控的产品料号的采样数据
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CCRAFT_AUDIT_MAN | string | 是 | - | 工艺审核人，对应TBL_SYS_USER.CUSER_NAME |
| CCRAFT_AUDIT_STATUS | int? | 是 | - | 工艺审核状态 |
| CCRAFT_AUDIT_TIME | DateTime? | 是 | - | 工艺审核时间 |
| CINPUT_TIME | DateTime | 否 | - | 录入时间 |
| CINPUT_VALUE1 | decimal | 否 | - | 输入值1 |
| CINPUT_VALUE2 | decimal | 否 | - | 输入值2 |
| CINPUT_VALUE3 | decimal | 否 | - | 输入值3 |
| CINPUT_VALUE4 | decimal | 否 | - | 输入值4 |
| CINPUT_VALUE5 | decimal | 否 | - | 输入值5 |
| CINPUT_VALUE6 | decimal | 否 | - | 输入值6 |
| CIPQA_AUDIT_MAN | string | 是 | - | IPQA审核人，对应TBL_SYS_USER.CUSER_NAME |
| CIPQA_AUDIT_STATUS | int? | 是 | - | IPQA审核状态 |
| CIPQA_AUDIT_TIME | DateTime? | 是 | - | IPQA审核时间 |
| CIS_NG | string | 是 | - | 是否NG，Y：是；N：否 |
| CITEM_ID | long? | 是 | - | 外键，产品ID,对应TBL_BD_ITEM.CID |
| CITEM_NAME | string | 是 | - | 物料名称 |
| CNG_REASON | string | 是 | - | NG原因 |
| CQA_AUDIT_MAN | string | 是 | - | 品保审核人，对应TBL_SYS_USER.CUSER_NAME |
| CQA_AUDIT_STATUS | int? | 是 | - | 品保审核状态 |
| CQA_AUDIT_TIME | DateTime? | 是 | - | 品保审核时间 |
| CQUALITY_AUDIT_MAN | string | 是 | - | 品质工程审核人，对应TBL_SYS_USER.CUSER_NAME |
| CQUALITY_AUDIT_STATUS | int? | 是 | - | 品质工程审核状态 |
| CQUALITY_AUDIT_TIME | DateTime? | 是 | - | 品质工程审核时间 |
| CREASON_ANALYSIS | string | 是 | - | 原因分析 |
| CREDRESS_MEASURE | string | 是 | - | 纠正措施 |
| CSOURCE | long? | 是 | - | 数据来源 |
| CTEMP_NAME | string | 是 | - | 模板名称 |
| CTYPE | int | 否 | - | 图类型（1单值图上图、2单值图下图、3均值图上图、4均值图下图） |
| CVALUE | decimal | 否 | - | 统计值 |
| CVARIABLE_ID | long | 否 | - | 管控特性ID，对应TBL_SPC_CONTROL_CHARACTERISTIC.CID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_SPC_DATA_REAL.CVARIABLE_ID = TBL_SPC_CONTROL_CHARACTERISTIC.CID
  - TBL_SPC_DATA_REAL.CITEM_ID = TBL_BD_ITEM.CID
  - TBL_SPC_DATA_REAL.CCRAFT_AUDIT_MAN = TBL_SYS_USER.CUSER_NAME
  - TBL_SPC_DATA_REAL.CIPQA_AUDIT_MAN = TBL_SYS_USER.CUSER_NAME
  - TBL_SPC_DATA_REAL.CQA_AUDIT_MAN = TBL_SYS_USER.CUSER_NAME
  - TBL_SPC_DATA_REAL.CQUALITY_AUDIT_MAN = TBL_SYS_USER.CUSER_NAME

---

#### 171 SPC判异规则定义表 ( TBL_SPC_RULE_OF_DISSENT )
- **业务含义**：描述具体的SPC判异规则
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CCOUNT | string | 是 | - | 判异次数/数量条件 |
| CDESC | string | 是 | - | 规则描述 |
| CTYPE | int | 否 | - | 规则类型 |
| CID | long | 否 | - | 主键 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_SPC_RULE_OF_DISSENT.CID = TBL_SPC_CONTROL_CHARACTERISTIC_RULE_LINK.CRULE_ID

---

### 2.13 出货报告

> 本章节数据来源于 Excel 工作表：`出货报告`

#### 172 出货报告生成 ( TBL_OQC_SHIPMENT_GENERATE )
- **业务含义**：包含已经生成的出货报告的生成过程的相关信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CFILES | string | 是 | - | 生成文件信息 |
| CGENERATE_QTY | int | 否 | - | 生成次数，按报告、型号、周期递增 |
| CGENERATE_REASON | string | 是 | - | 生成原因 |
| CGENERATE_TIME | DateTime | 否 | - | 生成时间 |
| CGENERATE_USER | string | 是 | - | 生成人，对应TBL_SYS_USER.CUSER_NAME |
| CITEM_NO | string | 是 | - | 型号，对应TBL_BD_ITEM.CITEM_NO |
| CLOG_ID | long | 否 | - | 生成记录ID，对应TBL_OQC_SHIPMENT_GENERATE_LOG.CID |
| CPARAMS | string | 是 | - | 生成参数(JSON字符串) |
| CPERIOD | string | 是 | - | 周期 |
| CREPORT_CODE | string | 是 | - | 报告编号 |
| CREPORT_ID | long | 否 | - | 报告ID，对应TBL_OQC_SHIPMENT_REPORT.CID |
| CREPORT_NAME | string | 是 | - | 报告名称 |
| CSO_NO | string | 是 | - | 订单号 |
| CID | long | 否 | - | 主键 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_OQC_SHIPMENT_GENERATE.CITEM_NO = TBL_BD_ITEM.CITEM_NO
  - TBL_OQC_SHIPMENT_GENERATE.CREPORT_ID = TBL_OQC_SHIPMENT_REPORT.CID
  - TBL_OQC_SHIPMENT_GENERATE.CGENERATE_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_OQC_SHIPMENT_GENERATE.CID = TBL_OQC_SHIPMENT_GENERATE_LOG.CGENERATE_ID
  - TBL_OQC_SHIPMENT_GENERATE.CLOG_ID = TBL_OQC_SHIPMENT_GENERATE_LOG.CID

---

#### 173 出货报告生成记录 ( TBL_OQC_SHIPMENT_GENERATE_LOG )
- **业务含义**：包含生成出货报告的日志信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CAUDIT_REMARK | string | 是 | - | 审核备注 |
| CAUDIT_STATUS | Enum_AuditStatus | 否 | - | 审核结果 |
| CAUDIT_TIME | DateTime? | 是 | - | 确认时间 |
| CAUDIT_USER | string | 是 | - | 确认人，对应TBL_SYS_USER.CUSER_NAME |
| CFILES | string | 是 | - | 生成文件信息 |
| CFILES_OLD | string | 是 | - | 旧版本生成文件信息 |
| CGENERATE_ID | long | 否 | - | 报告生成ID，对应TBL_OQC_SHIPMENT_GENERATE.CID |
| CGENERATE_QTY | int | 否 | - | 生成次数，按GENERATE_ID递增 |
| CGENERATE_REASON | string | 是 | - | 生成原因 |
| CGENERATE_TIME | DateTime | 否 | - | 生成时间 |
| CGENERATE_USER | string | 是 | - | 生成人，对应TBL_SYS_USER.CUSER_NAME |
| CIS_NEW | bool | 否 | - | 是否最新 |
| CITEM_NO | string | 是 | - | 型号，对应TBL_BD_ITEM.CITEM_NO |
| CPARAMS | string | 是 | - | 生成参数(JSON字符串) |
| CPARAMS_OLD | string | 是 | - | 旧版本生成参数(JSON字符串) |
| CPERIOD | string | 是 | - | 周期 |
| CREPORT_CODE | string | 是 | - | 报告编号 |
| CREPORT_ID | long | 否 | - | 报告ID，对应TBL_OQC_SHIPMENT_REPORT.CID |
| CREPORT_NAME | string | 是 | - | 报告名称 |
| CSO_NO | string | 是 | - | 订单号 |
| CID | long | 否 | - | 主键 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_OQC_SHIPMENT_GENERATE_LOG.CGENERATE_ID = TBL_OQC_SHIPMENT_GENERATE.CID
  - TBL_OQC_SHIPMENT_GENERATE_LOG.CREPORT_ID = TBL_OQC_SHIPMENT_REPORT.CID
  - TBL_OQC_SHIPMENT_GENERATE_LOG.CITEM_NO = TBL_BD_ITEM.CITEM_NO
  - TBL_OQC_SHIPMENT_GENERATE_LOG.CAUDIT_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_OQC_SHIPMENT_GENERATE_LOG.CGENERATE_USER = TBL_SYS_USER.CUSER_NAME

---

#### 174 出货报告料号关联表 ( TBL_OQC_SHIPMENT_ITEM_LINK )
- **业务含义**：描述了出货报告与产品料号的关联信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CITEM_ID | long? | 是 | - | 外键，产品或物料ID  对应TBL_BD_ITEM.CID |
| CREPORT_ID | long | 否 | - | 报告ID，对应TBL_OQC_SHIPMENT_REPORT.CID |
| CSEQ | int | 否 | - | 排序 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_OQC_SHIPMENT_ITEM_LINK.CITEM_ID = TBL_BD_ITEM.CID
  - TBL_OQC_SHIPMENT_ITEM_LINK.CREPORT_ID = TBL_OQC_SHIPMENT_REPORT.CID

---

#### 175 出货报告表 ( TBL_OQC_SHIPMENT_REPORT )
- **业务含义**：包含所有的出货报告列表
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CCODE | string | 是 | - | 报告编号 |
| CDESC | string | 是 | - | 描述 |
| CNAME | string | 是 | - | 报告名称 |
| CTYPE_ID | long? | 是 | - | 报告类型ID，对应TBL_OQC_SHIPMENT_REPORT_TYPE.CID |
| CID | long | 否 | - | 主键 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_OQC_SHIPMENT_REPORT.CTYPE_ID = TBL_OQC_SHIPMENT_REPORT_TYPE.CID
  - TBL_OQC_SHIPMENT_REPORT.CID = TBL_OQC_SHIPMENT_GENERATE.CREPORT_ID
  - TBL_OQC_SHIPMENT_REPORT.CID = TBL_OQC_SHIPMENT_GENERATE_LOG.CREPORT_ID
  - TBL_OQC_SHIPMENT_REPORT.CID = TBL_OQC_SHIPMENT_ITEM_LINK.CREPORT_ID

---

#### 176 出货报告类型表 ( TBL_OQC_SHIPMENT_REPORT_TYPE )
- **业务含义**：描述了出货报告的类型信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CTYPE_CODE | string | 是 | - | 类型编码 |
| CTYPE_DESC | string | 是 | - | 类型描述 |
| CTYPE_NAME | string | 是 | - | 类型名称 |
| CID | long | 否 | - | 主键 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_OQC_SHIPMENT_REPORT_TYPE.CID = TBL_OQC_SHIPMENT_REPORT.CTYPE_ID

---

### 2.14 锁机锁卡

> 本章节数据来源于 Excel 工作表：`锁机锁卡`

#### 177 模板与工作中心关联采集设备 ( TBL_PM_TEMPLATE_LINK_DEVICE )
- **业务含义**：描述设备点检模板与工作中心和设备信息关联信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CDEVICE_ID | long? | 是 | - | 设备ID， 对应TBL_EAP_DEVICE.CDEVICE_ID |
| CDEVICE_NAME | string | 是 | - | 设备名称 |
| CDEVICE_NO | string | 是 | - | 设备编号 |
| CPM_TEMPLATE_WC_LINK_ID | long? | 是 | - | 模板工作中心关联ID，对应TBL_EAM_PM_TEMP_WC_LINK.CID |
| CREMARK | string | 是 | - | 服务器地址备注 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_PM_TEMPLATE_LINK_DEVICE.CPM_TEMPLATE_WC_LINK_ID = TBL_EAM_PM_TEMP_WC_LINK.CID
  - TBL_PM_TEMPLATE_LINK_DEVICE.CDEVICE_ID = TBL_EAP_DEVICE.CDEVICE_ID

---

#### 178 锁机锁卡读码记录表 ( TBL_SJSKDATA_YYYYMM )
- **业务含义**：以分表的形式描述了每个月的锁机锁卡模块的读码记录，如TBL_SJSKDATA_202605
- **所属数据库**：192.168.49.16.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CDATETIME_CREATED | DateTime? | 是 | - | 读码时间 |
| CITEM_ID | string | 是 | - | 读码料号，对应TBL_BD_ITEM.CITEM_NO |
| CLOT_ID | string | 是 | - | 工单料号，对应TBL_BD_ITEM.CITEM_NO |
| EQPID | string | 是 | - | 设备ID |
| PANEL_LOT | string | 是 | - | 面板批次，对应TBL_MO.CMO_LOT |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_SJSKDATA_YYYYMM.CITEM_ID = TBL_BD_ITEM.CITEM_NO
  - TBL_SJSKDATA_YYYYMM.CLOT_ID = TBL_BD_ITEM.CITEM_NO
  - TBL_SJSKDATA_YYYYMM.PANEL_LOT = TBL_MO.CMO_LOT

---

#### 179 读码设备实时工单信息表 ( TBL_SJSKEQPINFO )
- **业务含义**：描述每个锁机锁卡设备实时状态信息
- **所属数据库**：192.168.49.18.CIEAP
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CURRENTITEM | string | 是 | - | 当前料号，对应TBL_BD_ITEM.CITEM_NO |
| CURRENTLOT | string | 是 | - | 当前工单，对应TBL_MO.CMO_LOT |
| EQPIP | string | 是 | - | 设备IP |
| EQPNAME | string | 是 | - | 设备名称 |
| NEXTITEM | string | 是 | - | 下一料号 |
| NEXTLOT | string | 是 | - | 下一工单 |
| UpdateTime | DateTime? | 是 | - | 更新时间 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_SJSKEQPINFO.CURRENTITEM = TBL_BD_ITEM.CITEM_NO
  - TBL_SJSKEQPINFO.CURRENTLOT = TBL_MO.CMO_LOT

---

#### 180 设备报警项关联配置表 ( TBL_EAP_ALARM_CONTROL_LINK )
- **业务含义**：包含了每个锁机锁卡设备需要关联的报警TAG配置信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CALARM_NAME | string | 是 | - | 报警名称 |
| CDEVICE_ID | int | 否 | - | 设备ID， 对应TBL_EAP_DEVICE.CDEVICE_ID |
| CREMARK | string | 是 | - | 备注 |
| CTAG_ID | long? | 是 | - | 测点ID（关联测点配置）, 对应TBL_EAP_TAG.CTAG_ID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAP_ALARM_CONTROL_LINK.CDEVICE_ID = TBL_EAP_DEVICE.CDEVICE_ID
  - TBL_EAP_ALARM_CONTROL_LINK.CTAG_ID = TBL_EAP_TAG.CTAG_ID

---

#### 181 设备关联料号 ( TBL_EAP_ITEM_CONTROL_LINK )
- **业务含义**：包含了每个锁机锁卡设备需要关联的可放行料号的配置信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CDEVICE_ID | int | 否 | - | 设备ID， 对应TBL_EAP_DEVICE.CDEVICE_ID |
| CITEM_ID | long? | 是 | - | 外键，产品ID  对应TBL_BD_ITEM.CID |
| CREMARK | string | 是 | - | 备注 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAP_ITEM_CONTROL_LINK.CDEVICE_ID = TBL_EAP_DEVICE.CDEVICE_ID
  - TBL_EAP_ITEM_CONTROL_LINK.CITEM_ID = TBL_BD_ITEM.CID

---

#### 182 设备关联药水化验项目 ( TBL_EAP_POTION_ITEM_CONTROL_LINK )
- **业务含义**：包含了每个锁机锁卡设备需要关联的药水化验项目的配置信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CDEVICE_ID | int | 否 | - | 设备ID， 对应TBL_EAP_DEVICE.CDEVICE_ID |
| CNP_ITEM_ID | long? | 是 | - | 化验模板项ID，对应TBL_NP_TEMPLATE_ITEM.CID |
| CREMARK | string | 是 | - | 备注 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAP_POTION_ITEM_CONTROL_LINK.CDEVICE_ID = TBL_EAP_DEVICE.CDEVICE_ID
  - TBL_EAP_POTION_ITEM_CONTROL_LINK.CNP_ITEM_ID = TBL_NP_TEMPLATE_ITEM.CID

---

#### 183 生产管控设备配置表 ( TBL_EAP_PRODUCE_CONTROL_DEVICE )
- **业务含义**：描述了每个需要管控的锁机锁卡设备配置信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CDEVICE_ID | long | 否 | - | 设备ID， 对应TBL_EAP_DEVICE.CDEVICE_ID |
| CDEVICE_NAME | string | 是 | - | 设备名称 |
| CEND_CONTROL | TimeSpan | 否 | - | 管控结束时间 |
| CFIRST_CHECK | string | 是 | - | 首检校验开关（Y启用，N或空禁用） |
| CINSPECTION_CHECK | string | 是 | - | 检验记录校验开关（Y启用，N或空禁用） |
| CIS_SET_SCREEN | string | 是 | - | 是否启用看板/画面设置 |
| CPARENT_DEVICE | string | 是 | - | 上级设备/父设备标识 |
| CPOTION_CHECK | string | 是 | - | 药水化验校验开关（Y启用，N或空禁用） |
| CPRODUCE_LOG_CHECK | string | 是 | - | 生产日志校验开关（Y启用，N或空禁用） |
| CREMARK | string | 是 | - | 备注 |
| CSTART_CONTROL | TimeSpan | 否 | - | 管控开始时间 |
| CTIME_CHECK | string | 是 | - | 时间段校验开关（Y启用，N或空禁用） |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_EAP_PRODUCE_CONTROL_DEVICE.CDEVICE_ID = TBL_EAP_DEVICE.CDEVICE_ID

---

### 2.15 其它信息

> 本章节数据来源于 Excel 工作表：`其它信息`

#### 184 图形电镀孔铜厚度测量 ( TBL_FA_TXDD_KTHD )
- **业务含义**：包含图形电镀各个孔铜测量点的厚度测量信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CCLKJ | string | 是 | - | 测量孔径 |
| CMAIN_ID | long | 否 | - | 主表ID，对应TBL_FA_TXDD_MAIN.CID |
| CT_DATA1 | string | 是 | - | 测量值1 |
| CT_DATA2 | string | 是 | - | 测量值2 |
| CT_DATA3 | string | 是 | - | 测量值3 |
| CT_DATA4 | string | 是 | - | 测量值4 |
| CT_DATA5 | string | 是 | - | 测量值5 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_FA_TXDD_KTHD.CMAIN_ID = TBL_FA_TXDD_MAIN.CID

---

#### 185 图像电镀FA信息主表 ( TBL_FA_TXDD_MAIN )
- **业务含义**：包含图形电镀FA主表相关信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CAGV_CCOPER | string | 是 | - | 平均铜厚 |
| CAUDIT_DESC | string | 是 | - | 审核描述 |
| CAUDIT_STATUS | int? | 是 | - | 审核状态：0：待审核、1：通过、2：驳回 |
| CAUDIT_TIME | DateTime? | 是 | - | 审核时间 |
| CAUDIT_USER | string | 是 | - | 审核人，对应TBL_SYS_USER.CUSER_NAME |
| CBD_COPPER_THICKNESS | string | 是 | - | 板底铜厚 |
| CCOPPER_THICKNESS | string | 是 | - | 铜厚 |
| CCREATOR | string | 是 | - | 制作 |
| CCS_CCOPER | string | 是 | - | C/S铜厚 |
| CDATE | DateTime? | 是 | - | 日期 |
| CDRILL_BIT | string | 是 | - | 钻咀规格 |
| CDTCSCS_AREA | string | 是 | - | 镀铜C/S面参数 |
| CDTCSCS_ASF | string | 是 | - | 镀铜C/S面参数 |
| CDTDDSJ | string | 是 | - | 镀铜电镀时间 |
| CDTDLMD | string | 是 | - | 镀铜电流密度 |
| CDTSSCS_AREA | string | 是 | - | 镀铜S/S面参数 |
| CDTSSCS_ASF | string | 是 | - | 镀铜S/S面参数 |
| CDXCSCS_AREA | string | 是 | - | 镀锡C/S面参数 |
| CDXCSCS_ASF | string | 是 | - | 镀锡C/S面参数 |
| CDXDDSJ | string | 是 | - | 镀锡电镀时间 |
| CDXDLMD | string | 是 | - | 镀锡电流密度 |
| CDXSSCS_AREA | string | 是 | - | 镀锡S/S面参数 |
| CDXSSCS_ASF | string | 是 | - | 镀锡S/S面参数 |
| CELEC_SIDE | string | 是 | - | 电镀挂板夹边 |
| CELEC_WINDOW | string | 是 | - | 电镀窗口 |
| CIC_TOLERANCE | string | 是 | - | IC公差 |
| CINSPECT_DDCS | string | 是 | - | 电镀参数：检测人，对应TBL_SYS_USER.CUSER_NAME |
| CINSPECT_GBFS | string | 是 | - | 挂板方式：检测人，对应TBL_SYS_USER.CUSER_NAME |
| CINSPECT_KTHD | string | 是 | - | 孔铜厚度：检测人，对应TBL_SYS_USER.CUSER_NAME |
| CINSPECT_QPBT | string | 是 | - | 切片表铜：检测人，对应TBL_SYS_USER.CUSER_NAME |
| CINSPECT_SKKJ | string | 是 | - | 蚀刻后孔径测量：检测人，对应TBL_SYS_USER.CUSER_NAME |
| CINSPECT_SKXK | string | 是 | - | 蚀刻后线宽：检测人，对应TBL_SYS_USER.CUSER_NAME |
| CINSPECT_ZKCS | string | 是 | - | 阻抗测试：检测人，对应TBL_SYS_USER.CUSER_NAME |
| CITEM_NO | string | 是 | - | 料号，对应TBL_BD_ITEM.CITEM_NO |
| CK_CCOPER | string | 是 | - | K值铜厚 |
| CLEN | decimal? | 是 | - | 长度 |
| CLINE | string | 是 | - | 线别 |
| CM_CCOPER | string | 是 | - | M值铜厚 |
| CMIN_LINE_SPACE | string | 是 | - | 最小线距 |
| CMIN_LINE_WIDE | string | 是 | - | 最小线宽 |
| CPLANK_QTY | string | 是 | - | 挂板数量 |
| CRESULT_KTHD | string | 是 | - | 孔铜厚度：判定结果；ACC：通过；REJ：不通过 |
| CRESULT_QPBT | string | 是 | - | 切片表铜：判定结果；ACC：通过；REJ：不通过 |
| CRESULT_SKKJ | string | 是 | - | 蚀刻后孔径测量：判定结果；ACC：通过；REJ：不通过 |
| CRESULT_SKXK | string | 是 | - | 蚀刻后线宽：判定结果；ACC：通过；REJ：不通过 |
| CRESULT_ZKCS | string | 是 | - | 阻抗测试：判定结果；ACC：通过；REJ：不通过 |
| CSAMPLE_QTY | int? | 是 | - | 抽样数量 |
| CSIZE | string | 是 | - | 尺寸 |
| CSS_CCOPER | string | 是 | - | S/S铜厚 |
| CTHICKNESS | string | 是 | - | 板厚 |
| CTIN_THICKNESS | string | 是 | - | 锡厚 |
| CWIDE | decimal? | 是 | - | 宽度 |
| CXK_TOLERANCE | string | 是 | - | 线宽管控公差 |
| CID | long | 否 | - | 主键 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_FA_TXDD_MAIN.CITEM_NO = TBL_BD_ITEM.CITEM_NO
  - TBL_FA_TXDD_MAIN.CAUDIT_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_FA_TXDD_MAIN.CCREATOR = TBL_SYS_USER.CUSER_NAME
  - TBL_FA_TXDD_MAIN.CINSPECT_DDCS = TBL_SYS_USER.CUSER_NAME
  - TBL_FA_TXDD_MAIN.CINSPECT_GBFS = TBL_SYS_USER.CUSER_NAME
  - TBL_FA_TXDD_MAIN.CINSPECT_KTHD = TBL_SYS_USER.CUSER_NAME
  - TBL_FA_TXDD_MAIN.CINSPECT_QPBT = TBL_SYS_USER.CUSER_NAME
  - TBL_FA_TXDD_MAIN.CINSPECT_SKKJ = TBL_SYS_USER.CUSER_NAME
  - TBL_FA_TXDD_MAIN.CINSPECT_SKXK = TBL_SYS_USER.CUSER_NAME
  - TBL_FA_TXDD_MAIN.CINSPECT_ZKCS = TBL_SYS_USER.CUSER_NAME
  - TBL_FA_TXDD_MAIN.CID = TBL_FA_TXDD_KTHD.CMAIN_ID
  - TBL_FA_TXDD_MAIN.CID = TBL_FA_TXDD_QPBT.CMAIN_ID
  - TBL_FA_TXDD_MAIN.CID = TBL_FA_TXDD_SKKJ.CMAIN_ID
  - TBL_FA_TXDD_MAIN.CID = TBL_FA_TXDD_SKXK.CMAIN_ID
  - TBL_FA_TXDD_MAIN.CID = TBL_FA_TXDD_XHCL.CMAIN_ID
  - TBL_FA_TXDD_MAIN.CID = TBL_FA_TXDD_ZKCS.CMAIN_ID

---

#### 186 图形电镀切片表铜 ( TBL_FA_TXDD_QPBT )
- **业务含义**：包含图形电镀切片表铜测量点的测量信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CBMTH1 | string | 是 | - | 表铜厚度1 |
| CBMTH2 | string | 是 | - | 表铜厚度2 |
| CBMTH3 | string | 是 | - | 表铜厚度3 |
| CBMTH4 | string | 是 | - | 表铜厚度4 |
| CDXCL1 | string | 是 | - | 锡层测量1 |
| CDXCL2 | string | 是 | - | 锡层测量2 |
| CINSPECT_USER | string | 是 | - | 检测人，对应TBL_SYS_USER.CUSER_NAME |
| CKCCL1 | string | 是 | - | 孔铜粗糙度1 |
| CKCCL2 | string | 是 | - | 孔铜粗糙度2 |
| CKNTHA | string | 是 | - | 孔内铜厚A |
| CKNTHB | string | 是 | - | 孔内铜厚B |
| CKNTHC | string | 是 | - | 孔内铜厚C |
| CKNTHD | string | 是 | - | 孔内铜厚D |
| CKNTHE | string | 是 | - | 孔内铜厚E |
| CKNTHF | string | 是 | - | 孔内铜厚F |
| CMAIN_ID | long | 否 | - | 主表ID，对应TBL_FA_TXDD_MAIN.CID |
| CRESULT | string | 是 | - | 判定结果；ACC：通过；REJ：不通过 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_FA_TXDD_QPBT.CMAIN_ID = TBL_FA_TXDD_MAIN.CID
  - TBL_FA_TXDD_QPBT.CINSPECT_USER = TBL_SYS_USER.CUSER_NAME

---

#### 187 图形电镀蚀刻后孔径测量 ( TBL_FA_TXDD_SKKJ )
- **业务含义**：包含图形电镀蚀刻后各孔径测量点的测量信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CDRILL_BIT | string | 是 | - | 钻咀规格 |
| CMAIN_ID | long | 否 | - | 主表ID，对应TBL_FA_TXDD_MAIN.CID |
| CMEASURED | string | 是 | - | 实测值 |
| CPRODUCT | string | 是 | - | 产品标准值 |
| CREMARK | string | 是 | - | 备注 |
| CRESULT | string | 是 | - | 判定结果；ACC：通过；REJ：不通过 |
| CTOLERANCE | string | 是 | - | 公差 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_FA_TXDD_SKKJ.CMAIN_ID = TBL_FA_TXDD_MAIN.CID

---

#### 188 图形电镀蚀刻后线宽 ( TBL_FA_TXDD_SKXK )
- **业务含义**：包含图形电镀蚀刻后线宽测量点的测量信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CBGAJX_SC | string | 是 | - | BGA间隙实测 |
| CBGAJX_YQ | string | 是 | - | BGA间隙要求 |
| CBGAKD_SC | string | 是 | - | BGA孔大实测 |
| CBGAKD_YQ | string | 是 | - | BGA孔大要求 |
| CGBDKD_SC | string | 是 | - | GBD孔大实测 |
| CGBDKD_YQ | string | 是 | - | GBD孔大要求 |
| CICJX_SC | string | 是 | - | IC间隙实测 |
| CICJX_YQ | string | 是 | - | IC间隙要求 |
| CICKD_SC | string | 是 | - | IC孔大实测 |
| CICKD_YQ | string | 是 | - | IC孔大要求 |
| CLAYER | string | 是 | - | 层别 |
| CMAIN_ID | long | 否 | - | 主表ID，对应TBL_FA_TXDD_MAIN.CID |
| CZXXK_SC | string | 是 | - | 阻焊线宽实测 |
| CZXXK_YQ | string | 是 | - | 阻焊线宽要求 |
| CZXXX_SC | string | 是 | - | 阻焊线隙实测 |
| CZXXX_YQ | string | 是 | - | 阻焊线隙要求 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_FA_TXDD_SKXK.CMAIN_ID = TBL_FA_TXDD_MAIN.CID

---

#### 189 图形电镀锡厚测量 ( TBL_FA_TXDD_XHCL )
- **业务含义**：包含图形电镀锡厚测量点的测量信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CMAIN_ID | long | 否 | - | 主表ID，对应TBL_FA_TXDD_MAIN.CID |
| CX_DATA1 | string | 是 | - | 锡厚数据1 |
| CX_DATA2 | string | 是 | - | 锡厚数据2 |
| CX_DATA3 | string | 是 | - | 锡厚数据3 |
| CX_DATA4 | string | 是 | - | 锡厚数据4 |
| CX_DATA5 | string | 是 | - | 锡厚数据5 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_FA_TXDD_XHCL.CMAIN_ID = TBL_FA_TXDD_MAIN.CID

---

#### 190 图形电镀阻抗测试 ( TBL_FA_TXDD_ZKCS )
- **业务含义**：包含图形电镀阻抗测量点的测量信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CLEVEL | string | 是 | - | 层别 |
| CMAIN_ID | long | 否 | - | 主表ID，对应TBL_FA_TXDD_MAIN.CID |
| CMEASURED | string | 是 | - | 实测值 |
| CREMARK | string | 是 | - | 备注 |
| CRESULT | string | 是 | - | 判定结果；ACC：通过；REJ：不通过 |
| CSTANDARD | string | 是 | - | 标准值 |
| CTOLERANCE | string | 是 | - | 公差 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_FA_TXDD_ZKCS.CMAIN_ID = TBL_FA_TXDD_MAIN.CID

---

#### 191 压合压机 ( TBL_FA_YHYJ_MAIN )
- **业务含义**：包含压合工序FA主表相关信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CAUDIT_DESC | string | 是 | - | 审核描述 |
| CAUDIT_PROCESS | string | 是 | - | 工艺审核 |
| CAUDIT_PRODUCE | string | 是 | - | 生产审核 |
| CAUDIT_QUALITY | string | 是 | - | 品质审核 |
| CAUDIT_STATUS | int? | 是 | - | 审核状态  0 ： 待审核 ; 1 ：审核通过 ;  2：审核不通过 |
| CAUDIT_TIME | DateTime? | 是 | - | 审核时间 |
| CAUDIT_USER | string | 是 | - | 审核人，对应TBL_SYS_USER.CUSER_NAME |
| CCORE_BOARD_THICKNESS | string | 是 | - | 芯板厚度 |
| CCREATOR1 | string | 是 | - | 制作人1，对应TBL_SYS_USER.CUSER_NAME |
| CCREATOR2 | string | 是 | - | 制作人2，对应TBL_SYS_USER.CUSER_NAME |
| CCREATOR3 | string | 是 | - | 制作人3，对应TBL_SYS_USER.CUSER_NAME |
| CDATE | DateTime? | 是 | - | 日期 |
| CERROR | string | 是 | - | 异常说明 |
| CINNER_COPPER_THICK | string | 是 | - | 内层铜厚 |
| CIPQC_SURE1 | string | 是 | - | IPQC确认1 |
| CIPQC_SURE2 | string | 是 | - | IPQC确认2 |
| CIS_BB | string | 是 | - | 是否爆板 |
| CIS_BDZW | string | 是 | - | 是否板底皱纹 |
| CIS_QPZH | string | 是 | - | 是否起泡折痕 |
| CITEM_NO | string | 是 | - | 料号，对应TBL_BD_ITEM.CITEM_NO |
| CPBKS | string | 是 | - | 排版块数 |
| CPP_SUPPLIER | string | 是 | - | PP供应商 |
| CPRESSED_STACKED | string | 是 | - | 压合叠板方式 |
| CRESIDUAL_COPPER_RATE | string | 是 | - | 残铜率 |
| CRESULT | string | 是 | - | 判定结果 |
| CTB_SPEC | string | 是 | - | 铜箔规格 |
| CX_CSCALE | string | 是 | - | X向涨缩 |
| CX_TARGET | string | 是 | - | X方向靶值汇总 |
| CX_TARGET1 | string | 是 | - | X靶值1 |
| CX_TARGET2 | string | 是 | - | X靶值2 |
| CX_TARGET3 | string | 是 | - | X靶值3 |
| CX_TARGET4 | string | 是 | - | X靶值4 |
| CX_TARGET5 | string | 是 | - | X靶值5 |
| CX_TARGET6 | string | 是 | - | X靶值6 |
| CY_CSCALE | string | 是 | - | Y向涨缩 |
| CY_TARGET | string | 是 | - | Y方向靶值 |
| CY_TARGET1 | string | 是 | - | Y靶值1 |
| CY_TARGET2 | string | 是 | - | Y靶值2 |
| CY_TARGET3 | string | 是 | - | Y靶值3 |
| CY_TARGET4 | string | 是 | - | Y靶值4 |
| CY_TARGET5 | string | 是 | - | Y靶值5 |
| CY_TARGET6 | string | 是 | - | Y靶值6 |
| CYB_PROGRAM | string | 是 | - | 压板程序 |
| CID | long | 否 | - | 主键 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_FA_YHYJ_MAIN.CITEM_NO = TBL_BD_ITEM.CITEM_NO
  - TBL_FA_YHYJ_MAIN.CAUDIT_USER = TBL_SYS_USER.CUSER_NAME
  - TBL_FA_YHYJ_MAIN.CCREATOR1 = TBL_SYS_USER.CUSER_NAME
  - TBL_FA_YHYJ_MAIN.CCREATOR2 = TBL_SYS_USER.CUSER_NAME
  - TBL_FA_YHYJ_MAIN.CCREATOR3 = TBL_SYS_USER.CUSER_NAME
  - TBL_FA_YHYJ_MAIN.CID = TBL_FA_YHYJ_MI.CMAIN_ID

---

#### 192 压合压机MI实测 ( TBL_FA_YHYJ_MI )
- **业务含义**：包含压机实际测量数据
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CJZHD_MI | string | 是 | - | 机组厚度MI值 |
| CJZHD_RESULT | string | 是 | - | 机组厚度判定 |
| CMAIN_ID | long | 否 | - | 主表ID，对应TBL_FA_YHYJ_MAIN.CID |
| CNCXBHD_MI | string | 是 | - | 内层芯板厚度MI值 |
| CNCXBHD_RESULT | string | 是 | - | 内层芯板厚度判定 |
| CYBHD_MI | string | 是 | - | 压板厚度MI值 |
| CYBHD_RESULT | string | 是 | - | 压板厚度判定 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_FA_YHYJ_MI.CMAIN_ID = TBL_FA_YHYJ_MAIN.CID

---

#### 193 重点物料参数维护 ( TBL_MEP_MATERIAL_PARAM )
- **业务含义**：包含重点产品料号和历史异常料号的相关参数维护信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CCONFIRMATION_TIME | DateTime? | 是 | - | 确认时间 |
| CCONFIRMED_USER | string | 是 | - | 确认人，对应TBL_SYS_USER.CUSER_NAME |
| CCONTROL_PLANS | string | 是 | - | 控制计划 |
| CDELIVERY_DATE | DateTime? | 是 | - | 交货日期  NPI流程专用 |
| CENTER_DATE | DateTime? | 是 | - | 下单日期  NPI流程专用 |
| CGROUP | string | 是 | - | 需确认组 |
| CITEM_ID | long | 否 | - | 料号，对应TBL_BD_ITEM.CID |
| CNOTES | string | 是 | - | 资料难点和注意事项 |
| CNPI_STATUS | string | 是 | - | 类型：NPI状态 NPI流程专用 |
| CPROCESS_ID | long | 否 | - | 工序，对应TBL_BD_PROCESS.CID |
| CQUANTITY | string | 是 | - | 数量 NPI流程专用 |
| CREASON | string | 是 | - | 跟进原因：来源数据字典：MEP_REASON |
| CSTATUS | long | 否 | - | 状态：1：待确认；2：已确认 |
| CTYPE | string | 是 | - | 类型：NPI--NPI流程 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - TBL_MEP_MATERIAL_PARAM.CITEM_ID = TBL_BD_ITEM.CID
  - TBL_MEP_MATERIAL_PARAM.CPROCESS_ID = TBL_BD_PROCESS.CID
  - TBL_MEP_MATERIAL_PARAM.CCONFIRMED_USER = TBL_SYS_USER.CUSER_NAME

---

#### 194 ERP包装信息视图 ( ERP_PACKEGE_INFO )
- **业务含义**：包含各产品的包装工序相关信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| 表面处理 | string? | 是 | - | 表面处理 |
| 层数 | int? | 是 | - | 层数 |
| 产品分组名称 | string? | 是 | - | 产品分组名称 |
| 客户物料描述 | string? | 是 | - | 客户物料描述 |
| 客户型号 | string? | 是 | - | 客户型号 |
| 拼板数 | string? | 是 | - | 拼板数 |
| 生产编号 | string | 是 | - | 生产编号，对应TBL_BD_ITEM.CITEM_NO |
| 终端产品编号 | string? | 是 | - | 终端产品编号 |
| 终端产品名称 | string? | 是 | - | 终端产品名称 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：无

---

#### 195 ERP中BOM领料单视图 ( VM_EAP_BOM_LIST )
- **业务含义**：包含ERP系统中的所有BOM领料记录信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| BatchNote | string | 是 | - | 批次备注 |
| BOMIssueCode | string | 是 | - | BOM发料单号 |
| BOMIssueDate | DateTime? | 是 | - | BOM发料日期 |
| BOMIssueNote | string | 是 | - | BOM发料备注 |
| BOMIssueStatus | string | 是 | - | BOM发料状态 |
| CategoryName | string | 是 | - | 类别名称 |
| Creator | string | 是 | - | 创建人 |
| Department | string | 是 | - | 部门 |
| EnterDate | DateTime? | 是 | - | 录入日期 |
| MaterialCode | string | 是 | - | 物料编码 |
| MaterialName | string | 是 | - | 物料名称 |
| MaterialStandard | string | 是 | - | 物料规格 |
| MfgPartCode | string | 是 | - | 制造部件号 |
| MOId | int? | 是 | - | MO标识 |
| MONumber | string | 是 | - | MO号 |
| MOType | string | 是 | - | MO类型 |
| PartNum | string | 是 | - | 料号，对应TBL_BD_ITEM.CITEM_NO |
| PickingCode | string | 是 | - | 领料单号 |
| PickingNote | string | 是 | - | 拣货备注 |
| Plants | string | 是 | - | 厂别 |
| Process | string | 是 | - | 生产工序，对应TBL_BD_PROCESS.CPROCESS_NAME |
| QtyIssued | decimal? | 是 | - | 发料数量 |
| QtyRemainIssued | decimal? | 是 | - | 已发料剩余数量 |
| QtySOVote | decimal? | 是 | - | SO分配数量 |
| RemainLength | decimal? | 是 | - | 剩余长度 |
| RemainWidth | decimal? | 是 | - | 剩余宽度 |
| RequestedDate | DateTime? | 是 | - | 需求日期 |
| SaleType | string | 是 | - | 销售类别 |
| SoNumber | string | 是 | - | 销售订单号 |
| Steps | string | 是 | - | 工序步骤 |
| Unit | string | 是 | - | 单位 |
| Warehouse | string | 是 | - | 仓库 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：无

---

#### 196 ERP中BOM领料单对应的工单列表 ( VM_EAP_BOM_LIST_WO )
- **业务含义**：包含ERP系统中的所有BOM领料记录对应的工单明细信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| AB | string | 是 | - | AB编号 |
| Active | int? | 是 | - | 是否激活；1：已激活；2：未激活 |
| MfgPartCode | string | 是 | - | 制造部件号 |
| MOId | int? | 是 | - | MO标识，对应VM_EAP_BOM_LIST.MOId |
| ParentId | string | 是 | - | 父级ID |
| partnum | string | 是 | - | 料号，对应TBL_BD_ITEM.CITEM_NO |
| qty_Array_BACKLOG | decimal? | 是 | - | 待处理阵列数量 |
| qty_PCS_BACKLOG | decimal? | 是 | - | 待处理PCS数量 |
| qty_PNL_BACKLOG | decimal? | 是 | - | 待处理板数量 |
| sheetLen | decimal? | 是 | - | 版面长度 |
| sheetWid | decimal? | 是 | - | 版面宽度 |
| Type | string | 是 | - | 类型 |
| WoNumber | string | 是 | - | 工单号，对应TBL_MO.CMO_LOT |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：无

---

#### 197 ERP中BOM发料记录视图 ( VM_ERP_BOM_ISSUE )
- **业务含义**：包含ERP系统中的所有BOM发料记录信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| 标准规格 | string | 是 | - | 标准规格 |
| 部门 | string | 是 | - | 部门 |
| 仓库 | string | 是 | - | 仓库 |
| 单位 | string | 是 | - | 单位 |
| 发料单号 | string | 是 | - | 发料单号 |
| 发料日期 | DateTime? | 是 | - | 发料日期 |
| 发料数量 | decimal? | 是 | - | 发料数量 |
| 工单编号 | string | 是 | - | 工单编号，对应TBL_MO.CMO_LOT |
| 工序 | string | 是 | - | 工序 |
| 工艺 | string | 是 | - | 工艺 |
| 供应商名称 | string | 是 | - | 供应商名称 |
| 供应商批号 | string | 是 | - | 供应商批号 |
| 寄售 | string | 是 | - | 寄售 |
| 领料单号 | string | 是 | - | 领料单号，对应VM_EAP_BOM_LIST.PickingCode |
| 内部批号 | string | 是 | - | 内部批号 |
| 请领日期 | DateTime? | 是 | - | 请领日期 |
| 投产数PCS | decimal? | 是 | - | 投产数PCS |
| 物料代码 | string | 是 | - | 物料代码 |
| 物料分组 | string | 是 | - | 物料分组 |
| 物料名称 | string | 是 | - | 物料名称 |
| 制单人员 | string | 是 | - | 制单人员 |
| 制造部件编码 | string | 是 | - | 制造部件编码，对应TBL_BD_ITEM.CITEM_NO |
| 制造单号 | string | 是 | - | 制造单号 |
| 制造单类型 | string | 是 | - | 制造单类型 |
| 状态 | string | 是 | - | 状态 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：无

---

#### 198 ERP中的IQC记录视图 ( VM_ERP_IQC_RESULT )
- **业务含义**：包含ERP系统中IQC记录信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CCHECK_NO | string | 是 | - | 检验单号 |
| CCHECK_TEMPLATE | string | 是 | - | 检验模板 |
| CCHECK_TIME | DateTime | 否 | - | 检验时间 |
| CCHECK_USER | string | 是 | - | 检验人员 |
| CITEM_NAME | string | 是 | - | 物料名称 |
| CITEM_NO | string | 是 | - | 物料编号，对应TBL_BD_ITEM.CITEM_NO |
| CSQE_RESULT | string | 是 | - | SQE结果；OK：通过 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - VM_ERP_IQC_RESULT.CITEM_NO = TBL_BD_ITEM.CITEM_NO

---

#### 199 ERP系统中非BOM发料的发料记录 ( VM_ERP_MATERIAL_ISSUE )
- **业务含义**：包含ERP系统中领料单发料的发料记录信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| 标准规格 | string | 是 | - | 标准规格 |
| 部门 | string | 是 | - | 部门 |
| 仓库 | string | 是 | - | 仓库 |
| 创建日期 | DateTime? | 是 | - | 创建日期 |
| 单位 | string | 是 | - | 单位 |
| 发料单号 | string | 是 | - | 发料单号 |
| 发料日期 | DateTime? | 是 | - | 发料日期 |
| 工序 | string | 是 | - | 工序，对应TBL_BD_PROCESS.CPROCESS_NAME |
| 工艺 | string | 是 | - | 工艺 |
| 供应商名称 | string | 是 | - | 供应商名称 |
| 供应商批号 | string | 是 | - | 供应商批号 |
| 寄售 | string | 是 | - | 寄售 |
| 类型 | string | 是 | - | 类型 |
| 领料单号 | string | 是 | - | 领料单号 |
| 领料人 | string | 是 | - | 领料人 |
| 内部批号 | string | 是 | - | 内部批号 |
| 数量 | decimal? | 是 | - | 数量 |
| 物料代码 | string | 是 | - | 物料代码，对应TBL_BD_ITEM.CITEM_NO |
| 物料分组 | string | 是 | - | 物料分组 |
| 物料名称 | string | 是 | - | 物料名称 |
| 制单人员 | string | 是 | - | 制单人员 |
| 状态 | string | 是 | - | 状态：完成；活动 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：无

---

#### 200 外协工序 ( VM_ERP_OS_PROCESS )
- **业务含义**：包含所有外协产品中所对应的外协工序
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| PartNum | string | 是 | - | 料号，对应TBL_BD_ITEM.CITEM_NO |
| Process | string | 是 | - | 工序名称，对应TBL_BD_PROCESS.CPROCESS_NAME |
| ProcessCode | string | 是 | - | 工序代码，对应TBL_BD_PROCESS.CPROCESS_NO |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：无

---

#### 201 SO与料号映射 ( VM_ERP_SO_MAP )
- **业务含义**：包含外协订单号与产品料号的映射关系
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| code | string | 是 | - | 编码 |
| jobId | string | 是 | - | 作业号 |
| materialsgroup | string | 是 | - | 物料分组 |
| mfgPartCode | string | 是 | - | 制造部件号 |
| partNum | string | 是 | - | 料号，对应TBL_BD_ITEM.CITEM_NO |
| soNumber | string | 是 | - | 销售订单号 |
| standard | string | 是 | - | 规格 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：无

---

#### 202 物料供应商信息 ( VM_ITEM_SUPPLIER )
- **业务含义**：物料与供应商名称的对应关系
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CODE | string | 是 | - | 物料编码，对应TBL_BD_ITEM.CITEM_NO |
| NAME | string | 是 | - | 供应商名称 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - VM_ITEM_SUPPLIER.CODE = TBL_BD_ITEM.CITEM_NO

---

#### 203 需FA工单 ( VM_M_NEED_FA )
- **业务含义**：包含需要做FA的工单列表
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| moNumber | string | 是 | - | MO号 |
| Partnum | string | 是 | - | 料号，对应TBL_BD_ITEM.CITEM_NO |
| woNumber | string | 是 | - | 工单号，对应TBL_MO.CMO_LOT |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：无

---

#### 204 产品与物料映射 ( VM_PRODUCT_MAPPING_ITEM )
- **业务含义**：包含部分产品与所使用的物料的关联关系信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| 材料类型 | string? | 是 | - | 材料类型 |
| 高 | decimal? | 是 | - | 高度 |
| 宽 | decimal? | 是 | - | 宽度 |
| 上铜 | string? | 是 | - | 上铜 |
| 是否含铜 | string | 是 | - | 是否含铜 |
| 水印 | string? | 是 | - | 水印 |
| 无卤素 | string? | 是 | - | 无卤素 |
| 下铜 | string? | 是 | - | 下铜 |
| 颜色 | string? | 是 | - | 颜色 |
| 长 | decimal? | 是 | - | 长度 |
| CTI | decimal? | 是 | - | CTI |
| JobId | int | 否 | - | 作业ID |
| MaterialCode | string | 是 | - | 物料编码，对应TBL_BD_ITEM.CITEM_NO |
| MaterialName | string | 是 | - | 物料名称 |
| MaterialStandard | string | 是 | - | 物料规格 |
| Partnum | string | 是 | - | 料号，对应TBL_BD_ITEM.CITEM_NO |
| TG值 | string? | 是 | - | TG值 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：无

---

#### 205 全量物料映射信息 ( VM_PRODUCT_MAPPING_ITEM_ALL )
- **业务含义**：包含具体物料对应相关制造数据参数的信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| 材料类型 | string | 是 | - | 材料类型 |
| 高 | decimal? | 是 | - | 高度 |
| 宽 | decimal? | 是 | - | 宽度 |
| 上铜 | string | 是 | - | 上铜 |
| 是否含铜 | string | 是 | - | 是否含铜 |
| 水印 | string | 是 | - | 水印 |
| 无卤素 | string | 是 | - | 无卤素 |
| 下铜 | string | 是 | - | 下铜 |
| 颜色 | string | 是 | - | 颜色 |
| 长 | decimal? | 是 | - | 长度 |
| CTI | decimal? | 是 | - | CTI |
| MaterialCode | string | 是 | - | 物料编码，对应TBL_BD_ITEM.CITEM_NO |
| MaterialName | string | 是 | - | 物料名称 |
| MaterialStandard | string | 是 | - | 物料规格 |
| TG值 | string | 是 | - | TG值 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：无

---

#### 206 ERP库位信息 ( VW_ERP_LOCATION )
- **业务含义**：包含ERP系统中维护的仓库库位信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| code | string | 是 | - | 库位编码 |
| ifActive | int | 否 | - | 是否激活；1：已激活；0：未激活 |
| name | string | 是 | - | 仓库名称 |
| recId | string | 是 | - | 记录ID |
| warehouseId | string | 是 | - | 仓库ID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：无

---

#### 207 ERP外协订单和料号 ( VW_ERP_OUTSOURCED_PO )
- **业务含义**：包含ERP中外协订单号和料号的关联关系
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| 供应商代码 | string | 是 | - | 供应商代码 |
| 供应商名称 | string | 是 | - | 供应商名称 |
| 销售订单号 | string | 是 | - | 销售订单号 |
| 外协订单号 | string | 是 | - | 外协订单号 |
| 生产编号 | string | 是 | - | 生产编号 |
| 数量 | int | 否 | - | 数量 |
| 订单状态 | string | 是 | - | 订单状态，Outsoucing：外协中；Shipped：已发货；Cancel：已取消；Close：已关闭；Valid：生效中 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：无

---

#### 208 ERP仓库信息 ( VW_ERP_WAREHOUSE )
- **业务含义**：包含ERP系统中维护的仓库信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| code | string | 是 | - | 仓库编码 |
| ifActive | int | 否 | - | 是否激活；1：已激活；0：未激活 |
| name | string | 是 | - | 仓库名称 |
| recId | string | 是 | - | 记录ID |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：无

---

#### 209 HTL状态信息 ( VW_HTL_STATUS )
- **业务含义**：水平线设备当前运行状态信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CBRAND | string | 是 | - | 品牌 |
| CDEVICE_NAME | string | 是 | - | 设备名称 |
| CTAG_NAME | string | 是 | - | 标签名称 |
| CVALUE | string | 是 | - | 状态值；分为 工作中、报警中、停机中 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：无

---

#### 210 产品料号特殊要求 ( VW_ITEM_REQUIRE )
- **业务含义**：包含部分产品料号在生产过程中的特殊要求
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| ParameterVal | string | 是 | - | 特殊要求 |
| partNum | string | 是 | - | 料号，对应TBL_BD_ITEM.CITEM_NO |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：无

---

#### 211 MI通用工序参数 ( VW_MI_PROCESS_GENERAL )
- **业务含义**：包含ERP系统中维护的MI各工序参数信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CITEM_NAME | string | 是 | - | 物料名称 |
| CITEM_NO | string | 是 | - | 物料编号，对应TBL_BD_ITEM.CITEM_NO |
| CITEM_VERSION | string | 是 | - | 物料版本 |
| CPARAM_NAME | string | 是 | - | 参数名称 |
| CPARAM_NO | int | 否 | - | 参数编号 |
| CPARAM_VALUE | string | 是 | - | 参数值 |
| CPD | string | 是 | - | PD |
| CPROCESS_NAME | string | 是 | - | 工艺名称 |
| CPROCESS_NO | string | 是 | - | 工艺编号，对应TBL_BD_PROCESS.CPROCESS_NO |
| CUNIT | string | 是 | - | 单位 |
| MfgPartCode | string | 是 | - | 制造部件号 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - VW_MI_PROCESS_GENERAL.CITEM_NO = TBL_BD_ITEM.CITEM_NO
  - VW_MI_PROCESS_GENERAL.CPROCESS_NO = TBL_BD_PROCESS.CPROCESS_NO

---

#### 212 工单关联制造部件号 ( VW_MO_MAPPING_ITEM )
- **业务含义**：包含工单关联的制造部件号信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| mfgPartCode | string | 是 | - | 制造部件号 |
| partNum | string | 是 | - | 料号，对应TBL_BD_ITEM.CITEM_NO |
| woNumber | string | 是 | - | 工单号，对应TBL_MO.CMO_LOT |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：无

---

#### 213 产品消耗PP数量明细 ( VW_PP_CONSUMPTION )
- **业务含义**：包含各产品需要消耗的pp面积的信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| code | string | 是 | - | 编码 |
| jobId | string | 是 | - | 作业号 |
| materialsId | string | 是 | - | 物料ID |
| MfgPartId | string | 是 | - | 制造部件ID |
| partnum | string | 是 | - | 料号，对应TBL_BD_ITEM.CITEM_NO |
| qty | decimal | 否 | - | 数量 |
| standard | string | 是 | - | 规格 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：无

---

#### 214 销售订单信息 ( VW_SO_INFO )
- **业务含义**：包含ERP系统中的所有销售订单信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| CSO_NO | string | 是 | - | 销售订单号 |
| CUSTOMER_NAME | string | 是 | - | 客户名称 |
| CUSTOMER_NO | string | 是 | - | 客户编号，对应TBL_BD_CUSTOMER.CUSTOMER_NO |
| CUSTOMER_PART_NAME | string | 是 | - | 客户料号名称 |
| CUSTOMER_SHORT_NAME | string | 是 | - | 客户简称 |
| DELIVERED_QTY | decimal? | 是 | - | 已交付数量 |
| FACTORY_NAME | string | 是 | - | 工厂名称 |
| INTERNAL_PART_NUM | string | 是 | - | 内部料号 |
| ORDER_QTY | decimal? | 是 | - | 订单数量 |
| PART_NUM | string | 是 | - | 料号，对应TBL_BD_ITEM.CITEM_NO |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：
  - VW_SO_INFO.PART_NUM = TBL_BD_ITEM.CITEM_NO
  - VW_SO_INFO.CUSTOMER_NO = TBL_BD_CUSTOMER.CUSTOMER_NO

---

#### 215 VCP统计信息 ( VW_VCP_STATISTIC )
- **业务含义**：包含VCP设备的生产数据统计信息
- **所属数据库**：192.168.49.10.CIMOM
| 字段名 | 字段类型 | 是否为空 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| 安培时 | decimal? | 是 | - | 安培时 |
| 理论镀铜量 | decimal? | 是 | - | 理论镀铜量 |
| 时间 | string | 是 | - | 时间 |
| CDEVICE_NAME | string | 是 | - | VCP设备名称编号 |
| CSTATE | string | 是 | - | 状态标识，A：有效；D：无效 |
- **关联关系**：无

---

## 三、表关系说明

### 3.1 表关系占位说明

当前输入数据中未包含明确的主键、外键及关系定义信息，以下内容为自动补充的占位章节：

- 可补充主键字段，例如 `CID`、`ID` 等。
- 可补充外键字段及其关联主表，例如 `CPARENT_ID -> TBL_SYS_PARAM_TYPE.CID`。
- 可补充一对一、一对多、多对多等业务关系。
- 如后续 Excel 中增加关系描述列，可在脚本中扩展自动生成关系图或关系表。

### 3.2 推荐补充模板

| 主表 | 外键表 | 关系类型 | 说明 |
|------|--------|----------|------|
| 待补充 | 待补充 | 待补充 | 待补充 |

## 四、数据字典速查

### 4.1 表清单

| 序号 | 表名 | 表注释 | 所属数据库 | 字段数量 |
|------|------|----------|------------|----------|
| 1 | TBL_SYS_DICTIONARY | 数据字典 | 192.168.49.10.CIMOM | 17 |
| 2 | TBL_SYS_ORGANIZATION | 组织机构表 | 192.168.49.10.CIMOM | 4 |
| 3 | TBL_SYS_PARAM | 系统参数配置表 | 192.168.49.10.CIMOM | 13 |
| 4 | TBL_SYS_PARAM_TYPE | 系统参数分类表 | 192.168.49.10.CIMOM | 8 |
| 5 | TBL_SYS_ROLE | 系统角色表 | 192.168.49.10.CIMOM | 3 |
| 6 | TBL_SYS_SERVER | 系统服务配置表 | 192.168.49.10.CIMOM | 5 |
| 7 | TBL_SYS_TEMPLATE_CONFIG | 系统模板配置表 | 192.168.49.10.CIMOM | 8 |
| 8 | TBL_SYS_USER | 系统用户表 | 192.168.49.10.CIMOM | 17 |
| 9 | TBL_SYS_USER_ORG_MAP | 用户组织关系 | 192.168.49.10.CIMOM | 4 |
| 10 | TBL_SYS_USER_ROLE_MAP | 用户角色关系表 | 192.168.49.10.CIMOM | 2 |
| 11 | TBL_BD_CUSTOMER | 客户信息表 | 192.168.49.10.CIMOM | 3 |
| 12 | TBL_BD_ITEM | 产品和物料信息表 | 192.168.49.10.CIMOM | 22 |
| 13 | TBL_BD_ITEM_TYPE | 产品和物料类型表 | 192.168.49.10.CIMOM | 10 |
| 14 | TBL_BD_PROCESS | 工序工艺信息表 | 192.168.49.10.CIMOM | 13 |
| 15 | TBL_BD_PROCESS_OUTS | 外协产品工序表 | 192.168.49.10.CIMOM | 7 |
| 16 | TBL_BD_RULE | 编码规则定义表 | 192.168.49.10.CIMOM | 2 |
| 17 | TBL_BD_SUPPLIER | 供应商信息表 | 192.168.49.10.CIMOM | 12 |
| 18 | TBL_BD_TEMPLATE | 模板信息表 | 192.168.49.10.CIMOM | 6 |
| 19 | TBL_BD_TEMPLATE_GROUP | 模板分组表 | 192.168.49.10.CIMOM | 3 |
| 20 | TBL_BD_WC | 工作中心表 | 192.168.49.10.CIMOM | 7 |
| 21 | TBL_BD_WC_ITEMTYPE_LINK | 工作中心与物料类别关联 | 192.168.49.10.CIMOM | 3 |
| 22 | TBL_BD_WC_PROCESS_LINK | 工作中心与工序关系表 | 192.168.49.10.CIMOM | 3 |
| 23 | TBL_MD_DATASET | 数据集 | 192.168.49.10.CIMOM | 8 |
| 24 | TBL_MSG_EVENT | 消息事件表 | 192.168.49.10.CIMOM | 11 |
| 25 | TBL_MSG_GROUP | 消息群组 | 192.168.49.10.CIMOM | 5 |
| 26 | TBL_MSG_GROUP_USER | 消息群组和用户 | 192.168.49.10.CIMOM | 2 |
| 27 | TBL_MSG_PUSH_FREQUENCY | 预警频率配置表 | 192.168.49.10.CIMOM | 3 |
| 28 | TBL_MSG_SEND_LOG | 消息发送日志表 | 192.168.49.10.CIMOM | 10 |
| 29 | TBL_MSG_USER | 消息推送用户 | 192.168.49.10.CIMOM | 4 |
| 30 | TBL_EAP_ALARM | 设备报警记录 | 192.168.49.10.CIEAP、192.168.49.18.CIEAP | 12 |
| 31 | TBL_EAP_AOI_DETECTIONS | AOI或者VRS数据主表 | 192.168.49.18.CIEAP | 16 |
| 32 | TBL_EAP_AOI_DETECTIONS_DTL | AOI或VRS数据明细表 | 192.168.49.18.CIEAP | 12 |
| 33 | TBL_EAP_API_RECORDS | 联机API调用记录 | 192.168.49.10.CIEAP、192.168.49.18.CIEAP | 9 |
| 34 | TBL_EAP_AUTO_PULL_MACHINE | 放板机状态监控表，两分钟更新一次 | 192.168.49.10.CIMOM | 7 |
| 35 | TBL_EAP_BT_PARAM | 班通参数主表 | 192.168.49.10.CIMOM | 5 |
| 36 | TBL_EAP_BT_PARAM_DTL | 班通参数明细表 | 192.168.49.10.CIMOM | 7 |
| 37 | TBL_EAP_CURRENT_DATA | 联机测点TAG实时状态表 | 192.168.49.10.CIEAP、192.168.49.18.CIEAP | 12 |
| 38 | TBL_EAP_DATA_YYYYMM | 联机数据测点采集信息表(分表) | 192.168.49.10.CIEAP、192.168.49.18.CIEAP | 9 |
| 39 | TBL_EAP_DEVICE | 联机设备列表 | 192.168.49.10.CIEAP、192.168.49.18.CIEAP | 16 |
| 40 | TBL_EAP_GE_PARAM | 今明图电参数 | 192.168.49.10.CIMOM | 14 |
| 41 | TBL_EAP_GE_PARAM_CHANGE_LOG | 图电参数变更记录表 | 192.168.49.10.CIMOM | 13 |
| 42 | TBL_EAP_GE_PARAM_USE_LOG | 图电参数下发记录 | 192.168.49.10.CIMOM | 3 |
| 43 | TBL_EAP_GOLD_NICKEL_TESTER_RECORD | 金镍测试仪上传数据主表，沉金 | 192.168.49.10.CIMOM | 23 |
| 44 | TBL_EAP_GOLD_NICKEL_TESTER_RECORD_DETAIL | 金镍测试仪上传数据明细表，沉金 | 192.168.49.10.CIMOM | 4 |
| 45 | TBL_EAP_GOLD_NICKEL_TESTER_RECORD_SN | 金镍测试仪主表，沉锡 | 192.168.49.10.CIMOM | 17 |
| 46 | TBL_EAP_GOLD_NICKEL_TESTER_RECORD_SN_DETAIL | 金镍测试仪明细表，沉锡 | 192.168.49.10.CIMOM | 3 |
| 47 | TBL_EAP_HAOS_PARAM | 浩硕打靶机参数 | 192.168.49.10.CIMOM | 22 |
| 48 | TBL_EAP_HEARTBEAT | 放板机心跳记录 | 192.168.49.10.CIMOM | 3 |
| 49 | TBL_EAP_HONGSHENG_RECORDS | 宏胜裁磨机结批数据 | 192.168.49.18.CIEAP | 8 |
| 50 | TBL_EAP_HONGSHENG_TM_RECORDS | 宏胜测厚机测试数据 | 192.168.49.18.CIEAP | 40 |
| 51 | TBL_EAP_HQ_PRESS_PRODUCTION | 活全压机数据，每两分钟从Mysql采集 | 192.168.49.10.CIEAP | 50 |
| 52 | TBL_EAP_LDI_LOG | LDI生产日志记录表 | 192.168.49.10.CIMOM | 16 |
| 53 | TBL_EAP_LDI_PARAM | LDI参数 | 192.168.49.10.CIMOM | 20 |
| 54 | TBL_EAP_LWT_DETECTIONS | 班通检测主记录表 | 192.168.49.18.CIEAP | 12 |
| 55 | TBL_EAP_LWT_DETECTIONS_DTL | 班通检测明细记录表 | 192.168.49.18.CIEAP | 17 |
| 56 | TBL_EAP_MASON_DETECTIONS | 麦逊检测结果主表 | 192.168.49.18.CIEAP | 5 |
| 57 | TBL_EAP_MASON_DETECTIONS_DTL | 麦逊检测结果明细表 | 192.168.49.18.CIEAP | 18 |
| 58 | TBL_EAP_PATTERN_PLAT | 图形电镀检测主记录表 | 192.168.49.10.CIMOM | 11 |
| 59 | TBL_EAP_PATTERN_PLAT_ITEM | 图形电镀检测明细表 | 192.168.49.10.CIMOM | 6 |
| 60 | TBL_EAP_PERIOD | 设备状态时段记录表 | 192.168.49.10.CIEAP、192.168.49.18.CIEAP | 7 |
| 61 | TBL_EAP_PMS_CONTENT | 汉印喷印机内容配置表 | 192.168.49.10.CIEAP | 14 |
| 62 | TBL_EAP_PMS_PROD | 汉印生产记录主表 | 192.168.49.10.CIEAP | 8 |
| 63 | TBL_EAP_PMS_PROD_DTL | 汉印生产记录明细表 | 192.168.49.10.CIEAP | 6 |
| 64 | TBL_EAP_SHUTDOWN_RECORD | 放板机关机记录表 | 192.168.49.10.CIMOM | 5 |
| 65 | TBL_EAP_STATUS | 设备状态采集记录表 | 192.168.49.10.CIEAP、192.168.49.18.CIEAP | 19 |
| 66 | TBL_EAP_TAG | 测点配置表 | 192.168.49.10.CIEAP、192.168.49.18.CIEAP | 30 |
| 67 | TBL_EAP_THREE_D_DATA | 三次元数据 | 192.168.49.10.CIMOM | 25 |
| 68 | TBL_EAP_THREE_D_ITEM | 三次元数据明细 | 192.168.49.10.CIMOM | 13 |
| 69 | TBL_EAP_THREE_D_RECORD | 三次元文件记录主表 | 192.168.49.10.CIMOM | 7 |
| 70 | TBL_EAP_TIME_RANGE_CONTROL | 放板机时间范围管控 | 192.168.49.10.CIMOM | 4 |
| 71 | TBL_EAP_YUHUI_TEST_RECORDS | 誉汇测试记录主表 | 192.168.49.18.CIEAP | 10 |
| 72 | TBL_EAP_YUHUI_TEST_RECORDS_DTL | 誉汇测试记录明细表 | 192.168.49.18.CIEAP | 20 |
| 73 | TBL_ABNORMAL_DATA_POOL | 锁机锁卡异常数据表 | 192.168.49.10.CIMOM | 8 |
| 74 | TBL_PATTERN_HAOSHUO_PRODUCTION_RECORD | 浩硕图形电镀生产记录主表 | 192.168.49.18.CIEAP | 9 |
| 75 | TBL_PATTERN_HAOSHUO_PRODUCTION_RECORD_DTL | 浩硕图形电镀生产记录明细表 | 192.168.49.18.CIEAP | 12 |
| 76 | TBL_QM_ASSAY_LOG | 化验任务记录表 | 192.168.49.10.CIMOM | 27 |
| 77 | TBL_QM_ASSAY_LOG_ITEM | 化验任务明细表 | 192.168.49.10.CIMOM | 44 |
| 78 | TBL_QM_CC_EXCEPTION | 客诉异常报告信息表 | 192.168.49.10.CIMOM | 44 |
| 79 | TBL_QM_COMPLAINT | 品质投诉记录表 | 192.168.49.10.CIMOM | 18 |
| 80 | TBL_QM_COMPLAINT_IMAGE | 品质投诉图片表 | 192.168.49.10.CIMOM | 3 |
| 81 | TBL_QM_INSPECT_RECORD | 检验记录主表 | 192.168.49.10.CIMOM | 29 |
| 82 | TBL_QM_INSPECTION_RECORD_ITEM | 检验记录明细表 | 192.168.49.10.CIMOM | 27 |
| 83 | TBL_QM_MEDICINE_TANK | 药缸信息表 | 192.168.49.10.CIMOM | 5 |
| 84 | TBL_QM_PL_LOG | 物理实验室送检记录主表 | 192.168.49.10.CIMOM | 32 |
| 85 | TBL_QM_PL_LOG_ITEM | 物理实验室送检记录明细表 | 192.168.49.10.CIMOM | 24 |
| 86 | TBL_ESOP_CONTACT_FORM | 联络单信息表 | 192.168.49.10.CIMOM | 18 |
| 87 | TBL_ESOP_COUNTERSIGN | 4M文件会签信息表 | 192.168.49.10.CIMOM | 6 |
| 88 | TBL_ESOP_FILE | ESOP文件主表 | 192.168.49.10.CIMOM | 26 |
| 89 | TBL_ESOP_FILE_CATEGORY | ESOP文件目录表 | 192.168.49.10.CIMOM | 6 |
| 90 | TBL_ESOP_FILE_SIGN | 文件手写体信息 | 192.168.49.10.CIMOM | 4 |
| 91 | TBL_ESOP_FILE_TYPE | ESOP文件类型表 | 192.168.49.10.CIMOM | 5 |
| 92 | TBL_ESOP_TEMPORARY_CHANGE_ORDER | 4M临时变更单 | 192.168.49.10.CIMOM | 36 |
| 93 | TBL_FOURM_CHANGE_ITEM_LOG | 4M变更料号日志表 | 192.168.49.10.CIMOM | 4 |
| 94 | TBL_EAM_PM_TEMP_WC_LINK | 模板关联工作中心 | 192.168.49.10.CIMOM | 3 |
| 95 | TBL_NP_TEMPLATE | 模板主表 | 192.168.49.10.CIMOM | 4 |
| 96 | TBL_NP_TEMPLATE_CHANGE | 模板变更主表 | 192.168.49.10.CIMOM | 16 |
| 97 | TBL_NP_TEMPLATE_CHANGE_ITEM | 模板变更明细表 | 192.168.49.10.CIMOM | 66 |
| 98 | TBL_NP_TEMPLATE_ITEM | 模板项配置表 | 192.168.49.10.CIMOM | 36 |
| 99 | TBL_EAM_ERROR_CODE | 设备故障代码表 | 192.168.49.10.CIMOM | 5 |
| 100 | TBL_EAM_FREQUENCY | 设备保养频次配置表 | 192.168.49.10.CIMOM | 6 |
| 101 | TBL_EAM_MAINTAIN_TASK | 保养任务主表 | 192.168.49.10.CIMOM | 23 |
| 102 | TBL_EAM_MAINTAIN_TASK_CHANGE_LOG | 保养任务时间变更日志表 | 192.168.49.10.CIMOM | 4 |
| 103 | TBL_EAM_MAINTAIN_TASK_ITEM | 保养任务明细表 | 192.168.49.10.CIMOM | 34 |
| 104 | TBL_EAM_MAINTAIN_TASK_ITEM_IMG | 保养任务明细图片表 | 192.168.49.10.CIMOM | 2 |
| 105 | TBL_EAM_REPAIR | 维修工单主表 | 192.168.49.10.CIMOM | 30 |
| 106 | TBL_EAM_REPAIR_IMG | 维修图片记录表 | 192.168.49.10.CIMOM | 3 |
| 107 | TBL_EAM_REPAIR_MAN | 指派人员列表 | 192.168.49.10.CIMOM | 4 |
| 108 | TBL_EAM_REPAIR_MATERIAL | 维修耗材记录表 | 192.168.49.10.CIMOM | 4 |
| 109 | TBL_SFC_DBFC_USER | 叠板防错用户 | 192.168.49.10.CIMOM | 2 |
| 110 | TBL_SFC_PACKAGE | 包装信息表 | 192.168.49.10.CIMOM | 32 |
| 111 | TBL_SFC_PACKAGE_LABEL_LINK | 包装模板与物料/客户关联表 | 192.168.49.10.CIMOM | 4 |
| 112 | TBL_SFC_PACKAGE_LOG | 包装操作日志表 | 192.168.49.10.CIMOM | 3 |
| 113 | TBL_SFC_PACKAGE_RULE | 包装规则主表 | 192.168.49.10.CIMOM | 20 |
| 114 | TBL_SFC_PACKAGE_RULE_EXT | 包装规则扩展配置表 | 192.168.49.10.CIMOM | 26 |
| 115 | TBL_SFC_PACKAGE_RULE_LINK | 包装规则与物料/客户关联表 | 192.168.49.10.CIMOM | 4 |
| 116 | TBL_SFC_RECIPE_LOT | 不合格工单配方信息表 | 192.168.49.10.CIMOM | 19 |
| 117 | TBL_SFC_RECIPE_LOT_LINK | 不合格工单配方项目明细表 | 192.168.49.10.CIMOM | 24 |
| 118 | TBL_SFC_RECIPE_PRODUCT | 按产品维度的配方信息主表 | 192.168.49.10.CIMOM | 21 |
| 119 | TBL_SFC_RECIPE_PRODUCT_LINK | 产品配方项目明细表 | 192.168.49.10.CIMOM | 27 |
| 120 | TBL_SFC_WS_LOG | 生产记录表 | 192.168.49.10.CIMOM | 29 |
| 121 | TBL_SFC_WS_LOG_ITEM | 生产记录项目明细 | 192.168.49.10.CIMOM | 18 |
| 122 | TBL_SFC_WS_TEMPLATE_CONFIG | 工位报工模板配置表 | 192.168.49.10.CIMOM | 19 |
| 123 | TBL_SFC_WS_TEMPLATE_LINK | 工作中心与模板关联配置表 | 192.168.49.10.CIMOM | 4 |
| 124 | TBL_MO | 工单信息表 | 192.168.49.10.CIMOM | 22 |
| 125 | TBL_MO_OUTS | 外协工单信息表 | 192.168.49.10.CIMOM | 5 |
| 126 | TBL_OUTSOURCE_SHIFT_EMPLOYEE | 外协班次员工配置表 | 192.168.49.10.CIMOM | 6 |
| 127 | VW_ERP_OUTSOURCED_PO | ERP外协订单和料号 | 192.168.49.10.CIMOM | 7 |
| 128 | VIEW_Core_Materials | 物料详细参数视图 | 192.168.49.10.CIMOM | 15 |
| 129 | VM_ERP_MI_INFO | ERP 发料信息视图 | 192.168.49.10.CIMOM | 26 |
| 130 | VW_ERP_MO_DATE_CODE | ERP 工单日期码视图 | 192.168.49.10.CIMOM | 4 |
| 131 | VW_MI_PROCESS_GENERAL | MI工序通用参数视图 | 192.168.49.10.CIMOM | 5 |
| 132 | VW_MO_ROUTE | 工单工艺路线视图 | 192.168.49.10.CIMOM | 5 |
| 133 | VW_WIP_Online | 在线在制品工单统计视图 | 192.168.49.10.CIMOM | 6 |
| 134 | TBL_WMS_ITEM_BARCODE | 物料条码表 | 192.168.49.10.CIMOM | 32 |
| 135 | TBL_WMS_ITEM_PACKING_BARCODE | 物料包装条码表 | 192.168.49.10.CIMOM | 5 |
| 136 | TBL_WMS_LINE_RECORD | 线别仓操作记录 | 192.168.49.10.CIMOM | 15 |
| 137 | TBL_WMS_LOCATION | 仓库货位 | 192.168.49.10.CIMOM | 3 |
| 138 | TBL_WMS_MANTISSA_RECORD | 尾数仓操作记录 | 192.168.49.10.CIMOM | 13 |
| 139 | TBL_WMS_PICKING_LOG | MES领料记录 | 192.168.49.10.CIMOM | 4 |
| 140 | TBL_WMS_PICKING_LOG_DTL | 领料记录明细 | 192.168.49.10.CIMOM | 4 |
| 141 | TBL_WMS_WAREHOUSE | 仓库主数据表 | 192.168.49.10.CIMOM | 15 |
| 142 | TBL_WMS_WAREHOUSE_TYPE | 仓库类型 | 192.168.49.10.CIMOM | 12 |
| 143 | TBL_WMS_AREA | 仓库区域 | 192.168.49.10.CIMOM | 7 |
| 144 | TBL_WMS_BARCODE_SPLIT_RECORD | 条码拆分记录表 | 192.168.49.10.CIMOM | 6 |
| 145 | TBL_WMS_PRINT_LOG | 仓库物料标签打印日志表 | 192.168.49.10.CIMOM | 6 |
| 146 | TBL_WMS_STOCK_BARCODE_LINK | ERP库存与打印条码关联表 | 192.168.49.10.CIMOM | 3 |
| 147 | VM_ERP_FGI | ERP成品库存视图 | 192.168.49.10.CIMOM | 35 |
| 148 | VM_ERP_FGI_IN | ERP成品入库记录 | 192.168.49.10.CIMOM | 44 |
| 149 | VM_ERP_FGI_OUT | ERP成品出库记录 | 192.168.49.10.CIMOM | 83 |
| 150 | VM_ERP_IQC_RETURN | IQC检验退货记录 | 192.168.49.10.CIMOM | 20 |
| 151 | VM_ERP_MATERIAL_OUT_IN | 物料出入库记录 | 192.168.49.10.CIMOM | 17 |
| 152 | VM_ERP_MATERIAL_RETURN_ITEM | ERP退料记录明细 | 192.168.49.10.CIMOM | 26 |
| 153 | VM_ERP_MATERIAL_RETURN_REQUEST_ITEM | ERP退料申请明细 | 192.168.49.10.CIMOM | 25 |
| 154 | VM_ERP_RETURN_GI | ERP退货明细 | 192.168.49.10.CIMOM | 40 |
| 155 | VM_ERP_STOCK_INFO | ERP库存物料视图 | 192.168.49.10.CIMOM | 11 |
| 156 | TBL_SRM_PO | 采购单 | 192.168.49.10.CIMOM | 12 |
| 157 | TBL_SRM_PO_DELIVERY | 采购订单交付表 | 192.168.49.10.CIMOM | 19 |
| 158 | TBL_SRM_PO_DETAIL | 采购订单明细 | 192.168.49.10.CIMOM | 20 |
| 159 | TBL_SRM_RECEIVING | 收货单主表 | 192.168.49.10.CIMOM | 14 |
| 160 | TBL_SRM_RECEIVING_BARCODE | 收货单条码关联表 | 192.168.49.10.CIMOM | 2 |
| 161 | TBL_SRM_RECEIVING_DTL | 收货单明细表 | 192.168.49.10.CIMOM | 32 |
| 162 | TBL_SHEET_LINK_PP | 供应商替代关联表 | 192.168.49.10.CIMOM | 4 |
| 163 | TBL_WMS_PICKING_LOG | MES领料记录 | 192.168.49.10.CIMOM | 4 |
| 164 | TBL_WMS_PICKING_LOG_DTL | 领料记录明细 | 192.168.49.10.CIMOM | 4 |
| 165 | TBL_MO_BARCODE_PROD_LINK | 工单与条码生产关联表 | 192.168.49.10.CIMOM | 5 |
| 166 | TBL_SPC_CONTROL_CHARACTERISTIC | SPC管控特性主表 | 192.168.49.10.CIMOM | 24 |
| 167 | TBL_SPC_CONTROL_CHARACTERISTIC_ITEM_LINK | SPC管控特性与对象关联表 | 192.168.49.10.CIMOM | 5 |
| 168 | TBL_SPC_CONTROL_CHARACTERISTIC_LIMIT | SPC管控特性控制限配置表 | 192.168.49.10.CIMOM | 8 |
| 169 | TBL_SPC_CONTROL_CHARACTERISTIC_RULE_LINK | SPC管控特性与判异规则关联表 | 192.168.49.10.CIMOM | 3 |
| 170 | TBL_SPC_DATA_REAL | SPC实时采样数据表 | 192.168.49.10.CIMOM | 30 |
| 171 | TBL_SPC_RULE_OF_DISSENT | SPC判异规则定义表 | 192.168.49.10.CIMOM | 4 |
| 172 | TBL_OQC_SHIPMENT_GENERATE | 出货报告生成 | 192.168.49.10.CIMOM | 14 |
| 173 | TBL_OQC_SHIPMENT_GENERATE_LOG | 出货报告生成记录 | 192.168.49.10.CIMOM | 21 |
| 174 | TBL_OQC_SHIPMENT_ITEM_LINK | 出货报告料号关联表 | 192.168.49.10.CIMOM | 3 |
| 175 | TBL_OQC_SHIPMENT_REPORT | 出货报告表 | 192.168.49.10.CIMOM | 5 |
| 176 | TBL_OQC_SHIPMENT_REPORT_TYPE | 出货报告类型表 | 192.168.49.10.CIMOM | 4 |
| 177 | TBL_PM_TEMPLATE_LINK_DEVICE | 模板与工作中心关联采集设备 | 192.168.49.10.CIMOM | 5 |
| 178 | TBL_SJSKDATA_YYYYMM | 锁机锁卡读码记录表 | 192.168.49.16.CIMOM | 5 |
| 179 | TBL_SJSKEQPINFO | 读码设备实时工单信息表 | 192.168.49.18.CIEAP | 7 |
| 180 | TBL_EAP_ALARM_CONTROL_LINK | 设备报警项关联配置表 | 192.168.49.10.CIMOM | 4 |
| 181 | TBL_EAP_ITEM_CONTROL_LINK | 设备关联料号 | 192.168.49.10.CIMOM | 3 |
| 182 | TBL_EAP_POTION_ITEM_CONTROL_LINK | 设备关联药水化验项目 | 192.168.49.10.CIMOM | 3 |
| 183 | TBL_EAP_PRODUCE_CONTROL_DEVICE | 生产管控设备配置表 | 192.168.49.10.CIMOM | 12 |
| 184 | TBL_FA_TXDD_KTHD | 图形电镀孔铜厚度测量 | 192.168.49.10.CIMOM | 7 |
| 185 | TBL_FA_TXDD_MAIN | 图像电镀FA信息主表 | 192.168.49.10.CIMOM | 54 |
| 186 | TBL_FA_TXDD_QPBT | 图形电镀切片表铜 | 192.168.49.10.CIMOM | 17 |
| 187 | TBL_FA_TXDD_SKKJ | 图形电镀蚀刻后孔径测量 | 192.168.49.10.CIMOM | 7 |
| 188 | TBL_FA_TXDD_SKXK | 图形电镀蚀刻后线宽 | 192.168.49.10.CIMOM | 16 |
| 189 | TBL_FA_TXDD_XHCL | 图形电镀锡厚测量 | 192.168.49.10.CIMOM | 6 |
| 190 | TBL_FA_TXDD_ZKCS | 图形电镀阻抗测试 | 192.168.49.10.CIMOM | 7 |
| 191 | TBL_FA_YHYJ_MAIN | 压合压机 | 192.168.49.10.CIMOM | 44 |
| 192 | TBL_FA_YHYJ_MI | 压合压机MI实测 | 192.168.49.10.CIMOM | 7 |
| 193 | TBL_MEP_MATERIAL_PARAM | 重点物料参数维护 | 192.168.49.10.CIMOM | 14 |
| 194 | ERP_PACKEGE_INFO | ERP包装信息视图 | 192.168.49.10.CIMOM | 9 |
| 195 | VM_EAP_BOM_LIST | ERP中BOM领料单视图 | 192.168.49.10.CIMOM | 32 |
| 196 | VM_EAP_BOM_LIST_WO | ERP中BOM领料单对应的工单列表 | 192.168.49.10.CIMOM | 13 |
| 197 | VM_ERP_BOM_ISSUE | ERP中BOM发料记录视图 | 192.168.49.10.CIMOM | 25 |
| 198 | VM_ERP_IQC_RESULT | ERP中的IQC记录视图 | 192.168.49.10.CIMOM | 7 |
| 199 | VM_ERP_MATERIAL_ISSUE | ERP系统中非BOM发料的发料记录 | 192.168.49.10.CIMOM | 22 |
| 200 | VM_ERP_OS_PROCESS | 外协工序 | 192.168.49.10.CIMOM | 3 |
| 201 | VM_ERP_SO_MAP | SO与料号映射 | 192.168.49.10.CIMOM | 7 |
| 202 | VM_ITEM_SUPPLIER | 物料供应商信息 | 192.168.49.10.CIMOM | 2 |
| 203 | VM_M_NEED_FA | 需FA工单 | 192.168.49.10.CIMOM | 3 |
| 204 | VM_PRODUCT_MAPPING_ITEM | 产品与物料映射 | 192.168.49.10.CIMOM | 17 |
| 205 | VM_PRODUCT_MAPPING_ITEM_ALL | 全量物料映射信息 | 192.168.49.10.CIMOM | 15 |
| 206 | VW_ERP_LOCATION | ERP库位信息 | 192.168.49.10.CIMOM | 5 |
| 207 | VW_ERP_OUTSOURCED_PO | ERP外协订单和料号 | 192.168.49.10.CIMOM | 7 |
| 208 | VW_ERP_WAREHOUSE | ERP仓库信息 | 192.168.49.10.CIMOM | 4 |
| 209 | VW_HTL_STATUS | HTL状态信息 | 192.168.49.10.CIMOM | 4 |
| 210 | VW_ITEM_REQUIRE | 产品料号特殊要求 | 192.168.49.10.CIMOM | 2 |
| 211 | VW_MI_PROCESS_GENERAL | MI通用工序参数 | 192.168.49.10.CIMOM | 11 |
| 212 | VW_MO_MAPPING_ITEM | 工单关联制造部件号 | 192.168.49.10.CIMOM | 3 |
| 213 | VW_PP_CONSUMPTION | 产品消耗PP数量明细 | 192.168.49.10.CIMOM | 7 |
| 214 | VW_SO_INFO | 销售订单信息 | 192.168.49.10.CIMOM | 10 |
| 215 | VW_VCP_STATISTIC | VCP统计信息 | 192.168.49.10.CIMOM | 4 |
