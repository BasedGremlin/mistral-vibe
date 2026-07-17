
# Game Design Fundamentals

## The Core Loop

Every game has a core loop — the fundamental action repeated throughout play.
Good core loops are: intuitive, immediately rewarding, and infinitely interesting.

```
Action → Feedback → Reward → New Action
  ↑___________________________|
```

**Examples:**
- Minecraft: Mine → Craft → Build → Mine (more resources)
- Dark Souls: Explore → Fight → Die → Learn → Explore (better)
- Stardew Valley: Plant → Wait → Harvest → Plant (more/different)

## The Four Fun Types (Lazzaro)

1. **Hard Fun** — challenge, achievement, problem-solving (Dark Souls, chess)
2. **Easy Fun** — curiosity, exploration, discovery (open-world games)
3. **Altered States** — immersion, emotion, narrative (story games, horror)
4. **People Fun** — competition, cooperation, social (multiplayer)

A great game often hits 2-3 of these. Know which you're designing for.

## Feedback Loops

### Positive Feedback (Snowball Effect)
Better player → more rewards → even better player
- Creates exciting comebacks and runaway leaders
- Too strong = one player dominates immediately
- Used well in: racing power-ups, kill streaks, economy games

### Negative Feedback (Rubber-Banding)
Better player → harder opponents → more balanced game
- Prevents dominant strategies from ending fun early
- Used well in: Mario Kart items, difficulty scaling, catch-up mechanics

## Flow Theory (Csikszentmihalyi)

The "flow state" sits between boredom (too easy) and anxiety (too hard).

```
Anxiety
    │        /flow state/
    │       ╱
    │      ╱
    │─────╱
    │    ╱
    │   ╱
    └──────────── Skill
Boredom
```

**Implementation:**
- Adaptive difficulty (scale enemies to player skill)
- Optional challenge rooms for skilled players
- Clear skill progression (player can see improvement)

## Juice: Making Things Feel Good

"Juice" = excessive positive feedback for simple actions.

Every action should have:
- **Visual feedback** (particle burst, screen shake, color flash)
- **Audio feedback** (satisfying sound, pitch variation)
- **Tactile feedback** (controller rumble if available)
- **Number feedback** (damage numbers, score popups)

Even a simple button press feels better with: a squash/stretch animation + click sound + brief color change.

## Economy Design

### Resource Management
Define your resources and their relationships:
- **Sources** — where resources come from
- **Sinks** — where resources are spent
- **Storage** — maximum held at once
- **Conversion** — trade one resource for another

### Inflation Prevention
- Time-gate valuable resources
- Make high-tier items cost multiple resource types
- Create meaningful spending decisions (player choice = engagement)

## Level Design Principles

1. **Teach through play** — introduce mechanics safely before requiring mastery
2. **Reward exploration** — secrets, shortcuts, optional challenge
3. **Readable spaces** — players should understand what a space is for at a glance
4. **Escalating complexity** — combine learned mechanics in new ways

### The 3 C's of Level Design
- **Contrast** — light/dark, open/closed, safe/dangerous areas
- **Color** — guide attention with color (red = danger, bright = reward)
- **Composition** — lead the eye toward the objective or point of interest

## Difficulty and Player Psychology

### Death and Checkpoints
- Punishing death = tension, investment, satisfaction
- Forgiving death = accessibility, pacing, momentum
- Rule: punishment should scale with difficulty, not game length
- Long levels need mid-level checkpoints to prevent frustration

### The Tutorial Problem
Players skip text tutorials. Teach via:
- Forced experience (locked room with only one solution)
- NPC demonstration (watch the AI do it)
- On-screen prompt at the exact moment it's relevant
- Let them fail first, then teach

## Narrative Integration

Good story and gameplay reinforce each other:
- **Ludonarrative harmony** — mechanics FEEL like the story (Celeste: hard platforming = anxiety/struggle)
- **Environmental storytelling** — world itself tells the story (ruins, journals, scars)
- **Agency** — player choices that matter to the narrative create investment

## Balancing Process

1. Design the intended experience
2. Build a minimal playable version
3. Playtest with fresh players (watch, don't explain)
4. Fix the 3 most frustrating moments
5. Repeat until fun

Never balance from your own playtesting alone — you know too much.
