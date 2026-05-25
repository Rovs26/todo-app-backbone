# Spec: Streak Stats

Combined requirements + design + tasks. Extends `fullstack-todo-app`.

## Goal

Show the user a "streak" of consecutive days they completed at least one todo, plus a few related counters, on the dashboard.

## Requirements

### Requirement 1: Read-only stats endpoint

#### Acceptance Criteria
1. WHEN `GET /api/todos/streak` is received from an authenticated user, THE Todo_Service SHALL return `{ today_completed, week_completed, current_streak_days, longest_streak_days, last_completion_date }`.
2. THE response SHALL be computed live from existing todos with `status == done` (no new persisted state).
3. `today_completed` SHALL count todos owned by the user whose `updated_at` date (UTC) equals today's date AND whose status is `done`.
4. `week_completed` SHALL count todos done in the last 7 calendar days (UTC), inclusive of today.
5. `current_streak_days` SHALL count consecutive days ending today on which the user completed at least one todo. If today has zero completions but yesterday had ≥1, the streak SHALL be the run ending yesterday plus 0 today (i.e., return the yesterday-anchored run unchanged until midnight UTC). At midnight the broken streak resets to 0.
6. `longest_streak_days` SHALL be the maximum run of consecutive completion-days observed across all the user's done todos.
7. `last_completion_date` SHALL be the most recent date a todo was marked done, or `null` if none.
8. THE endpoint SHALL be cheap (single pass over the user's todos) and SHALL NOT need a background job.

### Requirement 2: Frontend display

#### Acceptance Criteria
1. THE `StatsCards.vue` component SHALL render a new card "🔥 Streak" showing `current_streak_days` as the primary number with `longest_streak_days` as the subtitle.
2. THE card SHALL pull data from a new `useStreak()` composable that calls the endpoint, with a 60-second SWR pattern.
3. WHEN the user marks a todo done, THE composable SHALL invalidate its cache and refetch.

## Design

- New `services/streak_service.py` with a pure function `compute_streak(todos: list[Todo], now: datetime) -> StreakStats`. Pure means easy to property-test.
- New `models.py` addition: `StreakStats` Pydantic model.
- Add to `routers/todos.py` **before** the `/{todo_id}` block, alongside `/stats`.
- Algorithm:
  1. Collect set of UTC-date strings where the user has any done todo (use `updated_at` for completion proxy; this matches the existing pattern).
  2. Sort dates ascending.
  3. Walk to compute `longest_streak_days`.
  4. Walk from latest date backward to compute `current_streak_days` (counting today's date as eligible if `today` is in the set; otherwise count from yesterday).
- Frontend composable mirrors `useFolders.ts` shape.

## Tasks

- [ ] 1. Backend
  - [ ] 1.1 Add `StreakStats` to `models.py`
  - [ ] 1.2 Implement `services/streak_service.py:compute_streak` (pure function)
  - [ ] 1.3 Add `GET /api/todos/streak` to `routers/todos.py` (before `/{todo_id}`)
  - [ ]* 1.4 Pytest cases for `compute_streak`: zero todos; one today; consecutive run; broken streak; today empty but yesterday filled; cross-month boundary

- [ ] 2. Frontend
  - [ ] 2.1 Add `StreakStats` type and `todosApi.getStreak()` to `types/index.ts` and `utils/api.ts`
  - [ ] 2.2 Add `composables/useStreak.ts` with SWR + refetch-on-complete hook
  - [ ] 2.3 Add streak card to `StatsCards.vue`
  - [ ] 2.4 Wire `useStreak().invalidate()` into the existing todo update path when status flips to done

- [ ] 3. Verification
  - [ ] 3.1 pytest passes; manual: mark a todo done, see card update within ~1s
