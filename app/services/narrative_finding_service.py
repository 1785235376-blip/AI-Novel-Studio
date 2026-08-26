from dataclasses import asdict
from ..narrative_detection import NarrativeRuleContext,registry


class NarrativeFindingService:
 def __init__(self,repository):self.repository=repository
 def create_expectation(self,expectation):
  allowed={"THREAD_PROGRESS_BY":"THREAD","FORESHADOWING_PAYOFF_BY":"FORESHADOWING","MYSTERY_ANSWER_BY":"MYSTERY","CHARACTER_GOAL_PROGRESS_BY":"CHARACTER_GOAL"}
  if allowed.get(expectation.expectation_type)!=expectation.subject_type:raise ValueError("expectation type and subject type do not match")
  if expectation.deadline_chapter<1:raise ValueError("deadline_chapter must be positive")
  return self.repository.create(expectation.project_id,"expectations",asdict(expectation))
 def run_checks(self,context:NarrativeRuleContext):
  findings,successful_rules=registry.evaluate_isolated(context);active_ids={x.id for x in findings}
  for finding in findings:
   stored=self.repository.create(context.project_id,"findings",asdict(finding))
   if stored.get("status")=="RESOLVED":self.repository.set_status(context.project_id,"findings",finding.id,"OPEN")
  for stored in self.repository.list(context.project_id,"findings"):
   if stored.get("finding_type") in successful_rules and stored["id"] not in active_ids and stored.get("status")=="OPEN":self.repository.set_status(context.project_id,"findings",stored["id"],"RESOLVED")
  return findings
 def list_findings(self,project_id):return self.repository.list(project_id,"findings")
 def get_finding(self,project_id,finding_id):return self.repository.get(project_id,"findings",finding_id)
 def resolve(self,project_id,finding_id):return self.repository.set_status(project_id,"findings",finding_id,"RESOLVED")
