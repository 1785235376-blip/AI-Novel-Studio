from app.jobs import JobManager


class Persistence:
    def __init__(self):
        self.rows=[{
            "id":"interrupted","operation":"continue","novel_id":"n","chapter_id":"c",
            "instruction":"continue","profile":"LOCAL_ONLY","status":"GENERATING",
        }]
    def load_all(self):return self.rows
    def save(self,item):pass


def test_interrupted_job_becomes_safely_retryable_after_restart():
    manager=JobManager(generations=Persistence(),chapters=object(),contexts=object(),canon=object(),memory_extractor=object())
    job=manager.get("interrupted")
    assert job.status=="FAILED"
    assert job.error=="服务重启导致生成中断，请重新生成。"
