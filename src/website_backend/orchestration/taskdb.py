import sqlalchemy as sqla
import exorcist


class TaskStatusDB(exorcist.TaskStatusDB):
    @staticmethod
    def _create_empty_db(metadata, engine):
        task_type_table = sqla.Table(
            "task_types",
            metadata,
            sqla.Column("taskid", sqla.String, sqla.ForeignKey("tasks.taskid")),
            sqla.Column("task_type", sqla.String),
        )
        resource_lock_table = sqla.Table(
            "resource_locks",
            metadata,
            sqla.Column("resource", sqla.String),  # TODO: make this PK
            sqla.Column("taskid", sqla.String, sqla.ForeignKey("tasks.taskid")),
            sqla.Column("holder", sqla.String),
        )
        task_resources_table = sqla.Table(
            "task_resources",
            metadata,
            sqla.Column("taskid", sqla.String, sqla.ForeignKey("tasks.taskid")),
            sqla.Column("resource", sqla.String),
        )
        return exorcist.TaskStatusDB._create_empty_db(metadata, engine)

    @property
    def task_types_table(self):
        return self.metadata.tables["task_types"]

    @property
    def task_resources_table(self):
        return self.metadata.tables["task_resources"]

    @property
    def resource_locks_table(self):
        return self.metadata.tables["resource_locks"]

    def add_task(self, taskid, task_type, requirements, max_tries, task_resources=[]):
        # TODO: this should be improved by changing things on the exorcist
        # side so that this can all be one transaction
        super().add_task(taskid, requirements, max_tries)
        with self.engine.begin() as conn:
            conn.execute(
                sqla.insert(self.task_types_table).values(
                    [
                        {"taskid": taskid, "task_type": task_type},
                    ]
                )
            )
            for resource in task_resources:
                conn.execute(
                    sqla.insert(self.task_resources_table).values(
                        [
                            {"taskid": taskid, "resource": resource},
                        ]
                    )
                )
        # TODO: add support for adding resources

    def add_task_network(self, taskid_network, max_tries):
        super().add_task_network(taskid_network, max_tries)
        # TODO: this can be done in the internal methods
        task_types = [
            {"taskid": node, "task_type": taskid_network.nodes[node]["task_type"]}
            for node in taskid_network.nodes
        ]
        resources = {
            node: taskid_network.nodes[node]["task_resources"]
            for node in taskid_network.nodes
        }
        all_resources = set(sum(resources.values(), []))
        resources = []
        # TODO: paginate
        with self.engine.begin() as conn:
            conn.execute(sqla.insert(self.task_types_table).values(task_types))
            conn.execute(sqla.insert(self.task_resources_table).values(resources))

        self.initialize_resources(all_resources)

    def get_task_type(self, taskid):
        with self.engine.connect() as conn:
            res = list(
                conn.execute(
                    sqla.select(self.task_types_table).where(
                        self.task_types_table.c.taskid == taskid
                    )
                )
            )
        assert len(res) == 1
        return res[0].task_type

    def initialize_resources(self, resources):
        # resources start with no task and no holder
        with self.engine.begin() as conn:
            conn.execute(
                sqla.insert(self.resource_locks_table).values(
                    [
                        {"resource": resource, "taskid": None, "holder": None}
                        for resource in resources
                    ]
                )
            )

    def lock_resources_for_task(self, taskid, holder):
        # get all resources for a given task
        with self.engine.connect() as conn:
            res = list(
                conn.execute(
                    sqla.select(self.task_resources_table).where(
                        self.task_resources_table.c.taskid == taskid
                    )
                )
            )
        resources = [r.resource for r in res]

        # update each resource to have a lock
        with self.engine.begin() as conn:
            for resource in resources:
                conn.execute(
                    self.resource_locks_table.update()
                    .where(self.resource_locks_table.c.resource == resource)
                    .values(taskid=taskid, holder=holder)
                )

    def unlock_resources_for_task(self, taskid, holder):
        with self.engine.begin() as conn:
            conn.execute(
                self.resource_locks_table.update()
                .where(self.resource_locks_table.c.taskid == taskid)
                .values(taskid=None, holder=None)
            )
