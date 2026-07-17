import { describe, expect, it } from "vitest";
import { SwarmStateMachine } from "./state-machine";

describe("SwarmStateMachine", () => {
  it("accepts the canonical successful path", () => {
    const machine = new SwarmStateMachine();
    for (const state of [
      "PLAN",
      "ROUTE",
      "EXECUTE",
      "CRITIQUE",
      "VALIDATE",
      "PERSIST",
      "COMPLETE",
    ] as const) {
      machine.transition(state);
    }
    expect(machine.state).toBe("COMPLETE");
  });

  it("rejects validation bypass", () => {
    const machine = new SwarmStateMachine();
    machine.transition("PLAN");
    expect(() => machine.transition("COMPLETE")).toThrow(
      "Invalid swarm transition",
    );
  });

  it("can fail from any active state", () => {
    const machine = new SwarmStateMachine();
    machine.transition("PLAN");
    expect(machine.fail()).toBe("FAILED");
  });
});
