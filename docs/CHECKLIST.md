# System Design Checklist — Miktos Agentic System

Use this before building any new system or domain.
A system is not ready to build unless every item has a clear answer.

---

## A. Goal Definition
- [ ] What is the exact goal?
- [ ] What counts as success?
- [ ] What counts as partial success?
- [ ] What counts as failure?
- [ ] When must the system stop?

## B. State Awareness
- [ ] What is the current step?
- [ ] What tasks are pending?
- [ ] What already succeeded?
- [ ] What failed?
- [ ] What is blocked?
- [ ] What changed since last loop?

## C. Environment Awareness
- [ ] What tools are available?
- [ ] What permissions exist?
- [ ] What external systems can be touched?
- [ ] What constraints apply?
- [ ] What dependencies exist?

## D. Planning
- [ ] Can the goal be decomposed into tasks?
- [ ] Can tasks be ordered?
- [ ] Can dependencies be identified?
- [ ] Can parallel work be separated from sequential?

## E. Execution
- [ ] Which component performs the action?
- [ ] Which tool does it use?
- [ ] Can the action fail gracefully?
- [ ] Can it report status in structured form?

## F. Review / Validation
- [ ] What is being measured?
- [ ] What makes an output acceptable?
- [ ] What confidence threshold is required?
- [ ] Can the system detect uncertainty?

## G. Decision Gate
- [ ] What triggers retry?
- [ ] What triggers replan?
- [ ] What triggers escalation?
- [ ] What triggers stop?

## H. Correction Logic
- [ ] What changes after failure?
- [ ] Can parameters adjust?
- [ ] Can tools be swapped?
- [ ] Can scope be reduced?

## I. Memory
- [ ] What short-term state is stored?
- [ ] What long-term memory is stored?
- [ ] What must persist across sessions?

## J. Loop Discipline
- [ ] Maximum retries defined?
- [ ] Time budget defined?
- [ ] Confidence floor defined?
- [ ] Fallback behavior defined?

## K. Human Escalation
- [ ] What requires human judgment?
- [ ] What actions are irreversible?
- [ ] What safety boundaries exist?

## L. Output Integrity
- [ ] Is the result usable?
- [ ] Is confidence expressed?
- [ ] Are limitations exposed?

## M. Observability
- [ ] Are actions logged?
- [ ] Are decisions logged?
- [ ] Are failures logged?
- [ ] Can the path be reconstructed?

## N. Reusability
- [ ] Which parts are universal (engine)?
- [ ] Which parts are domain-specific?
- [ ] What can be reused across products?
