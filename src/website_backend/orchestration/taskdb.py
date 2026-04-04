import exorcist
import sqlalchemy as sqla


class TaskStatusDB(exorcist.TaskStatusDB):
    @staticmethod
    def _create_empty_db(metadata, engine):
        sqla.Table(
            "task_types",
            metadata,
            sqla.Column("taskid", sqla.String, sqla.ForeignKey("tasks.taskid")),
            sqla.Column("task_type", sqla.String),
        )
        sqla.Table(
            "task_details",
            metadata,
            sqla.Column("taskid", sqla.String, sqla.ForeignKey("tasks.taskid")),
            sqla.Column("task_details", sqla.JSON),
        )
        return exorcist.TaskStatusDB._create_empty_db(metadata, engine)

    @property
    def task_types_table(self):
        return self.metadata.tables["task_types"]

    @property
    def task_details_table(self):
        return self.metadata.tables["task_details"]

    def add_task(self, taskid, task_type, task_details, requirements, max_tries):
        super().add_task(taskid, requirements, max_tries)
        with self.engine.begin() as conn:
            conn.execute(
                sqla.insert(self.task_types_table).values(
                    {"taskid": taskid, "task_type": task_type}
                )
            )
            conn.execute(
                sqla.insert(self.task_details_table).values(
                    {"taskid": taskid, "task_details": task_details}
                )
            )

    def get_task_type(self, taskid):
        query = sqla.select(self.task_types_table.c.task_type).where(
            self.task_types_table.c.taskid == taskid
        )
        with self.engine.connect() as conn:
            return conn.execute(query).scalar_one()

    def get_task_details(self, taskid):
        query = sqla.select(self.task_details_table.c.task_details).where(
            self.task_details_table.c.taskid == taskid
        )
        with self.engine.connect() as conn:
            return conn.execute(query).scalar_one()

    def get_task_attempt(self, taskid):
        query = sqla.select(self.tasks_table.c.tries).where(
            self.tasks_table.c.taskid == taskid
        )
        with self.engine.connect() as conn:
            return conn.execute(query).scalar_one()
