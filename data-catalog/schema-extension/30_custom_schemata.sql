-- ***************************************

-------------------------------
-- Schema for AirFlow metadata
-------------------------------

CREATE SCHEMA airflow;

CREATE USER airflow_user WITH PASSWORD 'airflow_pass';

GRANT ALL PRIVILEGES ON SCHEMA airflow TO airflow_user;

------------------------------
-- Schema for MLFlow metadata 
-- NO LONGER USED
------------------------------

-- CREATE SCHEMA mlflow;

-- CREATE USER mlflow_user WITH PASSWORD 'mlflow_pass';

-- GRANT ALL PRIVILEGES ON SCHEMA mlflow TO mlflow_user;


--****************************************************************
--           Custom schema for WORKFLOW & TASK EXECUTIONS
--****************************************************************

CREATE SCHEMA klms;

-- Execution states for workflows & tasks

-- DROP TYPE state_enum;

CREATE TYPE state_enum AS ENUM ('created', 'restarting', 'running', 'removing', 'paused',  'dead', 'succeeded', 'failed');


---------------------------------------------
--           WORKFLOW EXECUTIONS
---------------------------------------------

-- DROP TABLE klms.workflow_execution;

CREATE TABLE klms.workflow_execution
( workflow_uuid varchar(64) NOT NULL,
  "state" state_enum NOT NULL, 
  start_date timestamp,
  end_date timestamp,
--  package_id text,
  PRIMARY KEY (workflow_uuid)
--,  CONSTRAINT fk_workflow_id FOREIGN KEY(package_id) REFERENCES public.package(id) ON UPDATE CASCADE ON DELETE CASCADE
);


-- DROP TABLE klms.workflow_tag;

CREATE TABLE klms.workflow_tag
( workflow_uuid varchar(64) NOT NULL,
  "key" text NOT NULL, 
  "value" text,
  PRIMARY KEY (workflow_uuid, "key"),
  CONSTRAINT fk_workflow_tag_uuid FOREIGN KEY(workflow_uuid) REFERENCES klms.workflow_execution(workflow_uuid) ON UPDATE CASCADE ON DELETE CASCADE
);

---------------------------------------------
--           TASK EXECUTIONS
---------------------------------------------

-- DROP TABLE klms.task_execution;

CREATE TABLE klms.task_execution
( task_uuid varchar(64) NOT NULL,
  workflow_uuid varchar(64) NOT NULL,
  "state" state_enum NOT NULL, 
  start_date timestamp,
  end_date timestamp,
  next_task_uuid varchar(64),
  PRIMARY KEY (task_uuid),
  CONSTRAINT fk_workflow_uuid FOREIGN KEY(workflow_uuid) REFERENCES klms.workflow_execution(workflow_uuid) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_next_task_uuid FOREIGN KEY(next_task_uuid) REFERENCES klms.task_execution(task_uuid) ON UPDATE CASCADE ON DELETE SET NULL
);


-- DROP TABLE klms.task_tag;

CREATE TABLE klms.task_tag
( task_uuid varchar(64) NOT NULL,
  "key" text NOT NULL, 
  "value" text,
  PRIMARY KEY (task_uuid, "key"),
  CONSTRAINT fk_task_tag_uuid FOREIGN KEY(task_uuid) REFERENCES klms.task_execution(task_uuid) ON UPDATE CASCADE ON DELETE CASCADE
);

-- DROP TABLE klms.metrics;

CREATE TABLE klms.metrics
( task_uuid varchar(64) NOT NULL,
  "key" text NOT NULL, 
  "value" text,
  issued timestamp,
  PRIMARY KEY (task_uuid, "key", issued),
  CONSTRAINT fk_task_metrics_uuid FOREIGN KEY(task_uuid) REFERENCES klms.task_execution(task_uuid) ON UPDATE CASCADE ON DELETE CASCADE
);


-- DROP TABLE klms.parameters;

CREATE TABLE klms.parameters
( task_uuid varchar(64) NOT NULL,
  "key" text NOT NULL, 
  "value" text,
  PRIMARY KEY (task_uuid, "key"),
  CONSTRAINT fk_task_parameters_uuid FOREIGN KEY(task_uuid) REFERENCES klms.task_execution(task_uuid) ON UPDATE CASCADE ON DELETE CASCADE
);


-- DROP TABLE klms.task_input;

CREATE TABLE klms.task_input
( task_uuid varchar(64) NOT NULL,
  dataset_id text NOT NULL, 
  PRIMARY KEY (task_uuid, dataset_id),
  CONSTRAINT fk_task_input_uuid FOREIGN KEY(task_uuid) REFERENCES klms.task_execution(task_uuid) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_task_input_dataset FOREIGN KEY(dataset_id) REFERENCES public.resource(id) ON UPDATE CASCADE ON DELETE CASCADE
);


-- DROP TABLE klms.task_output;

CREATE TABLE klms.task_output
( task_uuid varchar(64) NOT NULL,
  dataset_id text NOT NULL, 
  PRIMARY KEY (task_uuid, dataset_id),
  CONSTRAINT fk_task_output_uuid FOREIGN KEY(task_uuid) REFERENCES klms.task_execution(task_uuid) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_task_output_dataset FOREIGN KEY(dataset_id) REFERENCES public.resource(id) ON UPDATE CASCADE ON DELETE CASCADE
);

