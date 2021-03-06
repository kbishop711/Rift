"""
Copyright 2013-2014 Rackspace

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
import uuid
import falcon
import json
from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver
from paramiko import SSHException

from rift.api.common.resources import ApiResource
from rift.api.schemas import get_validator
from rift.api.schemas.job import job_schema
from rift.api.schemas.target import target_schema
from rift.api.schemas.schedule import schedule_schema
from rift.data.models.job import Job
from rift.data.models.job_execution import JobExecution
from rift.data.models.tenant import Tenant
from rift.data.models.target import Target
from rift.data.models.schedule import Schedule
from rift.clients.ssh import SSHClient, SSHKeyCredentials
from rift.actions import execute_job


class JobsResource(ApiResource):

    validator = get_validator(job_schema)

    def on_post(self, req, resp, tenant_id):
        body = self.load_body(req, self.validator)
        body['tenant_id'] = tenant_id

        job = Job.build_job_from_dict(body)
        Job.save_job(job)

        resp.status = falcon.HTTP_201
        resp.body = self.format_response_body({'job_id': job.id})

    def on_get(self, req, resp, tenant_id):
        jobs_list = [job.summary_dict() for job in Job.get_jobs(tenant_id)]
        resp.body = self.format_response_body({'jobs': jobs_list})


class JobResource(ApiResource):

    def on_get(self, req, resp, tenant_id, job_id):
        job = Job.get_job(job_id)
        if job:
            resp.body = self.format_response_body(job.as_dict())
        else:
            msg = 'Cannot find job: {job_id}'.format(job_id=job_id)
            resp.status = falcon.HTTP_404
            resp.body = json.dumps({'description': msg})

    def on_head(self, req, resp, tenant_id, job_id):
        job = Job.get_job(job_id)
        job_ex = JobExecution.build_job_from_dict(job.as_dict())

        if job:
            # TODO(jmv): Figure out scheduling of jobs
            JobExecution.save_job(job_ex)
            job.run_numbers.append(job_ex.run_number)
            Job.update_job(job)
            job = Job.get_job(job_id)

            execute_job.delay(job.id)
            resp.status = falcon.HTTP_200
        else:
            msg = 'Cannot find job: {job_id}'.format(job_id=job_id)
            resp.status = falcon.HTTP_404
            resp.body = json.dumps({'description': msg})

    def on_delete(self, req, resp, tenant_id, job_id):
        Job.delete_job(job_id=job_id)


class JobExecutionResource(ApiResource):

    def on_get(self, req, resp, tenant_id, job_id, run_number):
        job_execution = JobExecution.get_job(run_number)
        JobExecution.save_job(job_execution)
        if job_execution:
            resp.body = self.format_response_body(job_execution.as_dict())
        else:
            msg = 'Cannot find run number: {id}'.format(id=run_number)
            resp.status = falcon.HTTP_404
            resp.body = json.dumps({'description': msg})


class TenantsResource(ApiResource):

    def on_post(self, req, resp, tenant_id):
        body = self.load_body(req)
        body['tenant_id'] = tenant_id

        tenant = Tenant.build_tenant_from_dict(body)
        Tenant.save_tenant(tenant)

        resp.status = falcon.HTTP_201
        resp.body = self.format_response_body({'tenant_id': tenant.id})

    def on_get(self, req, resp, tenant_id):
        tenant = Tenant.get_tenant(tenant_id)
        if tenant:
            resp.body = self.format_response_body(tenant.as_dict())
        else:
            msg = 'Cannot find tenant: {tenant_id}'.format(tenant_id=tenant_id)
            resp.status = falcon.HTTP_404
            resp.body = json.dumps({'description': msg})

    def on_put(self, req, resp, tenant_id):
        tenant = Tenant.get_tenant(tenant_id)
        if tenant:
            body = self.load_body(req)
            body['tenant_id'] = tenant_id

            tenant = Tenant.build_tenant_from_dict(body)
            Tenant.update_tenant(tenant)
        else:
            msg = 'Cannot find tenant: {tenant_id}'.format(tenant_id=tenant_id)
            resp.status = falcon.HTTP_404
            resp.body = json.dumps({'description': msg})


class TargetsResource(ApiResource):

    validator = get_validator(target_schema)

    def on_post(self, req, resp, tenant_id):
        target_id = str(uuid.uuid4())

        body = self.load_body(req, self.validator)
        body['id'] = target_id

        target = Target.build_target_from_dict(tenant_id, body)
        duplicate_target = Target.get_target(tenant_id, target_id=target.name)

        if duplicate_target:
            raise falcon.exceptions.HTTPConflict(
                'Duplicate Target Name',
                'Target names must be unique: {0}'.format(target.name))

        Target.save_target(target)

        resp.status = falcon.HTTP_201
        resp.body = self.format_response_body({'target_id': target_id})

    def on_get(self, req, resp, tenant_id):
        targets = Target.get_targets(tenant_id)
        target_list = [target.summary_dict() for target in targets]

        resp.body = self.format_response_body({'targets': target_list})


class TargetResource(ApiResource):

    def on_get(self, req, resp, tenant_id, target_id):
        target = Target.get_target(tenant_id, target_id)
        if target:
            resp.body = self.format_response_body(target.as_dict())
        else:
            msg = 'Cannot find target: {target_id}'.format(target_id=target_id)
            resp.status = falcon.HTTP_404
            resp.body = json.dumps({'description': msg})

    def on_delete(self, req, resp, tenant_id, target_id):
        Target.delete_target(target_id=target_id)


class PingTargetResource(ApiResource):

    def on_get(self, req, resp, tenant_id, target_id):
        target = Target.get_target(tenant_id, target_id)
        if target:
            address = target.address
            # Nova
            if 'nova' in address.as_dict().keys():
                nova_address = address.address_child

                auth = target.authentication
                try:
                    if 'rackspace' in auth:
                        cls = get_driver(Provider.RACKSPACE)
                        cls(auth['rackspace']['username'],
                            auth['rackspace']['api_key'],
                            region=nova_address.region.lower())
                        resp.status = falcon.HTTP_200
                    else:
                        raise Exception("No supported providers in target: {0}"
                                        .format(target.as_dict()))
                except Exception:
                    resp.status = falcon.HTTP_404
            # SSH
            else:
                ip = address.address_child
                ssh = target.authentication.get('ssh')

                creds = SSHKeyCredentials(
                    username=ssh.get('username'),
                    key_contents=ssh.get('private_key')
                )
                client = SSHClient(
                    host=ip.address,
                    port=ip.port,
                    credentials=creds
                )
                try:
                    client.connect()
                    resp.status = falcon.HTTP_200
                    client.close()
                except SSHException:
                    resp.status = falcon.HTTP_404
        else:
            msg = 'Cannot find target: {target_id}'.format(target_id=target_id)
            resp.status = falcon.HTTP_404
            resp.body = json.dumps({'description': msg})


class SchedulesResource(ApiResource):

    validator = get_validator(schedule_schema)

    def on_get(self, req, resp, tenant_id):
        schedules_list = [
            s.as_dict() for s in Schedule.get_schedules(tenant_id)
        ]
        resp.body = self.format_response_body({'schedules': schedules_list})

    def on_post(self, req, resp, tenant_id):
        schedule_id = str(uuid.uuid4())
        body = self.load_body(req, self.validator)
        body['id'] = schedule_id

        schedule = Schedule.build_schedule_from_dict(tenant_id, body)

        Schedule.save_schedule(schedule)

        resp.status = falcon.HTTP_201
        resp.body = self.format_response_body({'schedule_id': schedule_id})


class ScheduleResource(ApiResource):

    def on_get(self, req, resp, tenant_id, schedule_id):
        schedule = Schedule.get_schedule(tenant_id, schedule_id)
        if schedule:
            resp.body = self.format_response_body(schedule.as_dict())
        else:
            self._not_found(resp, schedule_id)

    def on_head(self, req, resp, tenant_id, schedule_id):
        schedule = Schedule.get_schedule(tenant_id, schedule_id)
        if schedule:
            for entry in schedule.entries:
                execute_job.apply_async((entry.job_id,),
                                        countdown=entry.get_total_seconds())
            resp.status = falcon.HTTP_200
        else:
            self._not_found(resp, schedule_id)

    def on_delete(self, req, resp, tenant_id, schedule_id):
        Schedule.delete_schedule(schedule_id=schedule_id)

    def _not_found(self, resp, schedule_id):
        msg = 'Cannot find schedule: {0}'.format(schedule_id)
        resp.status = falcon.HTTP_404
        resp.body = json.dumps({'description': msg})
