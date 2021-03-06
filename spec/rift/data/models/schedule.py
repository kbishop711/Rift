import uuid

from specter import Spec, DataSpec, expect, skip

from rift.data.models.schedule import Schedule, Entry
from spec.rift.api.resources.fixtures import MockedDatabase


example_schedule_dict = {
    'id': '1234',
    'name': 'my schedule',
    'entries': [
        {
            "job_id": "job1",
            "delay": "01:02:03",
        }
    ]
}


class ScheduleModel(Spec):

    class Deserialization(Spec):

        def can_deserialize_from_a_dictionary(self):
            tenant_id = str(uuid.uuid4())
            schedule = Schedule.build_schedule_from_dict(
                tenant_id, example_schedule_dict)

            expect(schedule.tenant_id).to.equal(tenant_id)
            expect(schedule.schedule_id).to.equal('1234')
            expect(schedule.name).to.equal('my schedule')

            expect(schedule.entries[0].job_id).to.equal('job1')
            expect(schedule.entries[0].delay).to.equal("01:02:03")

    class Serialization(Spec):

        def can_serialize_to_a_dictionary(self):
            entry = Entry(job_id='job1', delay="01:02:03")
            schedule = Schedule(tenant_id='tenant1',
                                schedule_id='schedule1',
                                entries=[entry],
                                name='my schedule')

            schedule_dict = schedule.as_dict()
            expect(schedule_dict.get('id')).to.equal('schedule1')
            expect(schedule_dict.get('name')).to.equal('my schedule')
            expect(len(schedule_dict.get('entries', []))).to.equal(1)

            e = schedule_dict['entries'][0]
            expect(e.get('job_id')).to.equal('job1')
            expect(e.get('delay')).to.equal("01:02:03")

    class DatabaseActions(MockedDatabase):

        def before_each(self):
            super(type(self), self).before_each()
            self.tenant_id = str(uuid.uuid4())
            self.schedule = Schedule.build_schedule_from_dict(
                self.tenant_id, example_schedule_dict)
            Schedule.save_schedule(self.schedule)

        def can_save_and_get_a_schedule(self):
            found = Schedule.get_schedule(
                self.tenant_id, self.schedule.schedule_id)
            expect(found.as_dict()).to.equal(example_schedule_dict)

        def should_fail_to_get_missing_schedule(self):
            found = Schedule.get_schedule(self.tenant_id, str(uuid.uuid4()))
            expect(found).to.be_none()

        def can_get_schedules(self):
            schedules = Schedule.get_schedules(self.tenant_id)
            expect(len(schedules)).to.equal(1)
            expect(schedules[0].as_dict()).to.equal(example_schedule_dict)

        @skip('Fails - "not enough arguments for format string" in mongomock')
        def can_delete(self):
            Schedule.delete_schedule(self.schedule.schedule_id)
            found = Schedule.get_schedule(
                self.tenant_id, self.schedule.schedule_id)
            expect(found).to.be_none()

    class Entry(DataSpec):
        DATASET = {
            'zero_delay': {
                "delay": "00:00:00",
                "result": 0,
            },
            'delay_with_nonzero_seconds': {
                "delay": "00:00:93",
                "result": 93,
            },
            'delay_with_nonzero_minutes': {
                "delay": "00:84:00",
                "result": 5040,
            },
            'delay_with_nonzero_hours': {
                "delay": "67:00:00",
                "result": 241200,
            },
            'delay_with_hours_minutes_and_seconds': {
                "delay": "12:34:56",
                "result": 45296,
            },
        }

        def can_get_total_seconds_for(self, delay, result):
            entry = Entry(job_id=str(uuid.uuid4()), delay=delay)
            expect(entry.get_total_seconds()).to.equal(result)
