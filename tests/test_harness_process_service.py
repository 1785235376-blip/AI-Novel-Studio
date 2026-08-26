from app.services.harness_process_service import HarnessProcessService

def test_process_service_start_stop(monkeypatch):
    class P:
        pid=42
        def poll(self): return None
        def terminate(self): self.done=True
    holder=[]
    def popen(argv, **kwargs):
        assert kwargs['shell'] is False
        assert argv
        return holder.append(P()) or holder[-1]
    monkeypatch.setattr('subprocess.Popen', popen)
    service=HarnessProcessService(); assert service.start()['running'] is True; assert service.start()['pid']==42; assert service.last_action=='started'
    service.process.poll=lambda: 0
    assert service.stop()['running'] is False; assert service.last_action=='stopped'
