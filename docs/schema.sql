-- docs/schema.sql
-- 本文件是数据库唯一真相来源。任何变更必须先改此文件，经确认后再同步 ORM 与 Alembic。
-- MySQL 8.0 / utf8mb4 / InnoDB

CREATE TABLE t_user (
  id          BIGINT PRIMARY KEY AUTO_INCREMENT,
  username    VARCHAR(50)  NOT NULL UNIQUE COMMENT '登录名',
  password    VARCHAR(100) NOT NULL COMMENT 'bcrypt 哈希 ($2b$...)',
  role        VARCHAR(10)  NOT NULL DEFAULT 'user' COMMENT 'user|admin',
  status      TINYINT      NOT NULL DEFAULT 1 COMMENT '1启用 0禁用',
  created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表';

CREATE TABLE t_detection_task (
  id           BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id      BIGINT       NOT NULL COMMENT '关联 t_user.id',
  file_name    VARCHAR(255) NOT NULL COMMENT '原始文件名',
  file_path    VARCHAR(512) NOT NULL COMMENT '服务器存储路径',
  total_rows   INT          NOT NULL DEFAULT 0 COMMENT '总行数',
  attack_rows  INT          NOT NULL DEFAULT 0 COMMENT '判定为攻击的行数',
  normal_rows  INT          NOT NULL DEFAULT 0 COMMENT '判定为正常的行数',
  status       VARCHAR(20)  NOT NULL DEFAULT 'pending' COMMENT 'pending|running|success|failed',
  error_msg    VARCHAR(512) DEFAULT NULL,
  cost_seconds FLOAT        DEFAULT NULL,
  created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_user_time (user_id, created_at),
  INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='检测任务表';

CREATE TABLE t_detection_result (
  id          BIGINT PRIMARY KEY AUTO_INCREMENT,
  task_id     BIGINT       NOT NULL COMMENT '关联 t_detection_task.id',
  row_no      INT          NOT NULL COMMENT '文件中第几行（从1开始）',
  prediction  VARCHAR(20)  NOT NULL COMMENT 'Normal|Attack',
  attack_type VARCHAR(50)  DEFAULT NULL COMMENT '多分类时才有值',
  confidence  FLOAT        DEFAULT NULL COMMENT '置信度 0~1',
  INDEX idx_task (task_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='检测结果明细表';