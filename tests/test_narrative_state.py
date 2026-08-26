from app.narrative import *


def test_plot_thread_lifecycle_guards_terminal_state():
    thread=PlotThread("t","p","Investigation")
    transition_thread(thread,ThreadStatus.RESOLVED)
    try: transition_thread(thread,ThreadStatus.OPEN)
    except ValueError: pass
    else: raise AssertionError("resolved thread must be terminal")


def test_foreshadowing_payoff_requires_development_and_event():
    item=Foreshadowing("f","p","Locked door")
    transition_foreshadowing(item,ForeshadowingStatus.DEVELOPING)
    transition_foreshadowing(item,ForeshadowingStatus.PAYOFF,"event-payoff")
    assert item.payoff_event_id=="event-payoff"


def test_narrative_event_is_idempotently_reconstructed_and_project_isolated():
    thread=PlotThread("t","p","Thread")
    event=NarrativeEvent("e","p","THREAD_PROGRESS","t","chapter:1",("ev",),{"progress":"clue"})
    other=NarrativeEvent("x","other","THREAD_PROGRESS","t","chapter:1")
    view=NarrativeStateView("p",[thread]).reconstruct([event,event,other])
    assert thread.event_ids==["e"]
    assert [x.id for x in view.events]==["e"]
    assert event.fingerprint==event.fingerprint
