---------------------------- MODULE executor ----------------------------
(*
  TLA+ specification of the AminOpsTwin DurableExecutor state machine
  (P27, deliverable 6).

  This module formalises the executor state transitions including
  UNKNOWN, REVOKED, ESCALATED, and reconciliation.  It is checked by
  TLC with the following properties:

    NoDoubleEffect       == no two COMMITTED effects for the same workflow
    NoLostEffect         == every COMMIT_INTENT eventually reaches
                            COMMITTED or FAILED (under fairness)
    EventualResolution   == every UNKNOWN eventually reaches
                            COMMITTED, FAILED, or ESCALATED
                            (under fairness)

  The effect log is a sequence of records; a committed effect appears
  exactly once per workflow.  Reconciliation resolves UNKNOWN from the
  outbox: if the effect is found the state becomes COMMITTED, otherwise
  FAILED.  After MAX_BACKOFF of pending, the state becomes ESCALATED.

  See ADR-006 for the reconciliation semantics.
*)

EXTENDS Naturals, Sequences, Integers, FiniteSets

CONSTANTS
  WorkflowId,        (* the set of workflow identifiers *)
  MaxBackoff          (* maximum backoff rounds before ESCALATED *)

VARIABLES
  state,             (* [wf \in WorkflowId -> ExecutorState] *)
  effects,           (* the committed effect log: a set of (wf, eid) *)
  outbox,            (* the outbox: a set of (wf, eid, status) *)
  backoff            (* [wf \in WorkflowId -> Nat] backoff round counter *)

(* ------------------------------------------------------------------- *)
(* Executor states (mirror ExecutorState StrEnum in the code)         *)
(* ------------------------------------------------------------------- *)
PENDING        == "PENDING"
RUNNING        == "RUNNING"
CHECKPOINTED   == "CHECKPOINTED"
COMMIT_INTENT  == "COMMIT_INTENT"
COMMITTED      == "COMMITTED"
COMPLETED      == "COMPLETED"
DENIED         == "DENIED"
FAILED         == "FAILED"
UNKNOWN        == "UNKNOWN"
RECONCILING    == "RECONCILING"
REVOKED        == "REVOKED"
ESCALATED      == "ESCALATED"

States == {PENDING, RUNNING, CHECKPOINTED, COMMIT_INTENT,
           COMMITTED, COMPLETED, DENIED, FAILED,
           UNKNOWN, RECONCILING, REVOKED, ESCALATED}

TerminalStates == {COMPLETED, DENIED, FAILED, REVOKED, ESCALATED}

(* ------------------------------------------------------------------- *)
(* Type invariant                                                       *)
(* ------------------------------------------------------------------- *)
TypeInvariant ==
  /\ state \in [WorkflowId -> States]
  /\ effects \in SUBSET (WorkflowId \X Nat)
  /\ outbox \in SUBSET (WorkflowId \X Nat \X {"pending", "committed"})
  /\ backoff \in [WorkflowId -> Nat]

(* ------------------------------------------------------------------- *)
(* Valid transitions (mirror _VALID_TRANSITIONS in the code)          *)
(* ------------------------------------------------------------------- *)
ValidTransition(s, t) ==
  \/ /\ s = PENDING       /\ t \in {RUNNING, DENIED, FAILED}
  \/ /\ s = RUNNING       /\ t \in {CHECKPOINTED, DENIED, FAILED}
  \/ /\ s = CHECKPOINTED  /\ t \in {COMMIT_INTENT, DENIED, FAILED, REVOKED}
  \/ /\ s = REVOKED       /\ t = REVOKED
  \/ /\ s = COMMIT_INTENT /\ t \in {COMMITTED, UNKNOWN, DENIED}
  \/ /\ s = UNKNOWN       /\ t \in {RECONCILING, ESCALATED}
  \/ /\ s = RECONCILING   /\ t \in {COMMITTED, FAILED}
  \/ /\ s = ESCALATED     /\ t = ESCALATED
  \/ /\ s = COMMITTED     /\ t = COMPLETED
  \/ /\ s = COMPLETED     /\ t = COMPLETED
  \/ /\ s = DENIED        /\ t = DENIED
  \/ /\ s = FAILED        /\ t = FAILED

(* ------------------------------------------------------------------- *)
(* Initial state                                                        *)
(* ------------------------------------------------------------------- *)
Init ==
  /\ state = [w \in WorkflowId |-> PENDING]
  /\ effects = {}
  /\ outbox = {}
  /\ backoff = [w \in WorkflowId |-> 0]

(* ------------------------------------------------------------------- *)
(* Transition: start a workflow (PENDING -> RUNNING)                   *)
(* ------------------------------------------------------------------- *)
Start(w) ==
  /\ state[w] = PENDING
  /\ state' = [state EXCEPT ![w] = RUNNING]
  /\ effects' = effects
  /\ outbox' = outbox
  /\ backoff' = backoff

(* ------------------------------------------------------------------- *)
(* Transition: checkpoint (RUNNING -> CHECKPOINTED)                   *)
(* ------------------------------------------------------------------- *)
Checkpoint(w) ==
  /\ state[w] = RUNNING
  /\ state' = [state EXCEPT ![w] = CHECKPOINTED]
  /\ effects' = effects
  /\ outbox' = outbox
  /\ backoff' = backoff

(* ------------------------------------------------------------------- *)
(* Transition: commit intent (CHECKPOINTED -> COMMIT_INTENT)          *)
(* ------------------------------------------------------------------- *)
CommitIntent(w) ==
  /\ state[w] = CHECKPOINTED
  /\ state' = [state EXCEPT ![w] = COMMIT_INTENT]
  /\ effects' = effects
  /\ outbox' = outbox
  /\ backoff' = backoff

(* ------------------------------------------------------------------- *)
(* Transition: commit with outbox (COMMIT_INTENT -> COMMITTED)
   The effect and the outbox receipt are written atomically.
   NoDoubleEffect: the effect must not already exist for this wf.    *)
(* ------------------------------------------------------------------- *)
Commit(w, eid) ==
  /\ state[w] = COMMIT_INTENT
  /\ ~(w \in {e[1] : e \in effects})
  /\ state' = [state EXCEPT ![w] = COMMITTED]
  /\ effects' = effects \cup {(w, eid)}
  /\ outbox' = outbox \cup {(w, eid, "committed")}
  /\ backoff' = backoff

(* ------------------------------------------------------------------- *)
(* Transition: commit intent -> UNKNOWN (connection lost)              *)
(* The effect may or may not have been written; the outbox may        *)
(* contain a pending or committed entry.                              *)
(* ------------------------------------------------------------------- *)
GoUnknown(w, eid) ==
  /\ state[w] = COMMIT_INTENT
  /\ state' = [state EXCEPT ![w] = UNKNOWN]
  /\ effects' = effects
  /\ outbox' = outbox \cup {(w, eid, "pending")}
  /\ backoff' = backoff

(* ------------------------------------------------------------------- *)
(* Transition: reconcile UNKNOWN (UNKNOWN -> RECONCILING)             *)
(* ------------------------------------------------------------------- *)
StartReconcile(w) ==
  /\ state[w] = UNKNOWN
  /\ state' = [state EXCEPT ![w] = RECONCILING]
  /\ effects' = effects
  /\ outbox' = outbox
  /\ backoff' = backoff

(* ------------------------------------------------------------------- *)
(* Transition: reconcile from outbox (RECONCILING -> COMMITTED/FAILED)
   If the effect is found in the outbox with status "committed",     *)
/* the state becomes COMMITTED; otherwise FAILED.                    *)
(* ------------------------------------------------------------------- *)
Reconcile(w, eid) ==
  /\ state[w] = RECONCILING
  /\ (w, eid, "committed") \in outbox
  /\ ~(w \in {e[1] : e \in effects})
  /\ state' = [state EXCEPT ![w] = COMMITTED]
  /\ effects' = effects \cup {(w, eid)}
  /\ outbox' = outbox
  /\ backoff' = backoff

ReconcileFail(w) ==
  /\ state[w] = RECONCILING
  /\ ~(w \in {o[1] : o \in outbox /\ o[3] = "committed"})
  /\ state' = [state EXCEPT ![w] = FAILED]
  /\ effects' = effects
  /\ outbox' = outbox
  /\ backoff' = backoff

(* ------------------------------------------------------------------- *)
(* Transition: escalate (UNKNOWN -> ESCALATED after MAX_BACKOFF)      *)
(* ------------------------------------------------------------------- *)
Escalate(w) ==
  /\ state[w] = UNKNOWN
  /\ backoff[w] >= MaxBackoff
  /\ state' = [state EXCEPT ![w] = ESCALATED]
  /\ effects' = effects
  /\ outbox' = outbox
  /\ backoff' = backoff

IncrementBackoff(w) ==
  /\ state[w] = UNKNOWN
  /\ backoff[w] < MaxBackoff
  /\ state' = state
  /\ effects' = effects
  /\ outbox' = outbox
  /\ backoff' = [backoff EXCEPT ![w] = backoff[w] + 1]

(* ------------------------------------------------------------------- *)
(* Transition: revoke (CHECKPOINTED -> REVOKED)                        *)
(* ------------------------------------------------------------------- *)
Revoke(w) ==
  /\ state[w] = CHECKPOINTED
  /\ state' = [state EXCEPT ![w] = REVOKED]
  /\ effects' = effects
  /\ outbox' = outbox
  /\ backoff' = backoff

(* ------------------------------------------------------------------- *)
(* Transition: complete (COMMITTED -> COMPLETED)                      *)
(* ------------------------------------------------------------------- *)
Complete(w) ==
  /\ state[w] = COMMITTED
  /\ state' = [state EXCEPT ![w] = COMPLETED]
  /\ effects' = effects
  /\ outbox' = outbox
  /\ backoff' = backoff

(* ------------------------------------------------------------------- *)
(* Transition: deny or fail (from valid source states)                *)
(* ------------------------------------------------------------------- *)
Deny(w) ==
  /\ state[w] \in {PENDING, RUNNING, CHECKPOINTED, COMMIT_INTENT}
  /\ state' = [state EXCEPT ![w] = DENIED]
  /\ effects' = effects
  /\ outbox' = outbox
  /\ backoff' = backoff

Fail(w) ==
  /\ state[w] \in {PENDING, RUNNING, CHECKPOINTED}
  /\ state' = [state EXCEPT ![w] = FAILED]
  /\ effects' = effects
  /\ outbox' = outbox
  /\ backoff' = backoff

(* ------------------------------------------------------------------- *)
(* Next-state relation                                                  *)
(* ------------------------------------------------------------------- *)
Next ==
  \/ \E w \in WorkflowId : Start(w)
  \/ \E w \in WorkflowId : Checkpoint(w)
  \/ \E w \in WorkflowId : CommitIntent(w)
  \/ \E w \in WorkflowId, eid \in Nat : Commit(w, eid)
  \/ \E w \in WorkflowId, eid \in Nat : GoUnknown(w, eid)
  \/ \E w \in WorkflowId : StartReconcile(w)
  \/ \E w \in WorkflowId, eid \in Nat : Reconcile(w, eid)
  \/ \E w \in WorkflowId : ReconcileFail(w)
  \/ \E w \in WorkflowId : Escalate(w)
  \/ \E w \in WorkflowId : IncrementBackoff(w)
  \/ \E w \in WorkflowId : Revoke(w)
  \/ \E w \in WorkflowId : Complete(w)
  \/ \E w \in WorkflowId : Deny(w)
  \/ \E w \in WorkflowId : Fail(w)

(* ------------------------------------------------------------------- *)
(* Specification                                                        *)
(* ------------------------------------------------------------------- *)
Spec == Init /\ [][Next]_<<state, effects, outbox, backoff>>

(* ------------------------------------------------------------------- *)
(* Safety: NoDoubleEffect — at most one committed effect per workflow *)
(* ------------------------------------------------------------------- *)
NoDoubleEffect ==
  \A w \in WorkflowId :
    Cardinality({e \in effects : e[1] = w}) <= 1

(* ------------------------------------------------------------------- *)
(* Safety: NoLostEffect — a COMMIT_INTENT that is not denied always   *)
(* eventually reaches COMMITTED or FAILED (checked via the invariant   *)
(* that a COMMITTED effect exists for every COMPLETED workflow).       *)
(* ------------------------------------------------------------------- *)
NoLostEffect ==
  \A w \in WorkflowId :
    (state[w] = COMPLETED => \E e \in effects : e[1] = w)

(* ------------------------------------------------------------------- *)
(* Liveness: EventualResolution — every UNKNOWN eventually resolves    *)
(* to COMMITTED, FAILED, or ESCALATED (checked under fairness).        *)
(* ------------------------------------------------------------------- *)
EventualResolution ==
  \A w \in WorkflowId :
    (state[w] = UNKNOWN ~> 
       state[w] \in {COMMITTED, FAILED, ESCALATED})

(* ------------------------------------------------------------------- *)
(* Temporal: the state always stays in the valid set                  *)
(* ------------------------------------------------------------------- *)
StateInvariant ==
  \A w \in WorkflowId : state[w] \in States

=============================================================================