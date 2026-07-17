import type { SwarmState } from "./contracts";

const ALLOWED_TRANSITIONS: Record<SwarmState, readonly SwarmState[]> = {
  INTAKE: ["PLAN", "FAILED"],
  PLAN: ["ROUTE", "FAILED"],
  ROUTE: ["EXECUTE", "FAILED"],
  EXECUTE: ["CRITIQUE", "VALIDATE", "FAILED"],
  CRITIQUE: ["VALIDATE", "FAILED"],
  VALIDATE: ["PERSIST", "FAILED"],
  PERSIST: ["COMPLETE", "FAILED"],
  COMPLETE: [],
  FAILED: [],
};

export class SwarmStateMachine {
  private _state: SwarmState = "INTAKE";

  get state(): SwarmState {
    return this._state;
  }

  transition(next: SwarmState): SwarmState {
    if (!ALLOWED_TRANSITIONS[this._state].includes(next)) {
      throw new Error(`Invalid swarm transition: ${this._state} -> ${next}`);
    }
    this._state = next;
    return this._state;
  }

  fail(): SwarmState {
    if (this._state !== "COMPLETE" && this._state !== "FAILED") {
      this._state = "FAILED";
    }
    return this._state;
  }
}
