"""
Validated C/C++ programming verification task set with known ground truth
and controlled annotations for Standard, Explanation-Based, and Verification-Guided interfaces.

Includes:
- WARMUP_TASK: 1 unscored 12-line practice task to eliminate first-task UI learning-curve bias.
- VALIDATED_TASKS: 6 matched, realistic 35-55 line C++ problems across diverse domains
  (Pair Groups A, B, C; 1 correct + 1 subtly buggy per group) to prevent ceiling effects.
- SYSTEMS_COMPLEX_TASKS: 3 systems/kernel-flavored C++ tasks (including a 108-line SlabAllocator).
"""

WARMUP_TASK = {
    "id": "warmup_clamp_value",
    "title": "Warm-Up (Unscored): Clamp Integer to Range",
    "difficulty": "Practice",
    "task_set": "warmup",
    "problem_statement": (
        "Practice task (not scored): Review this short function `clampValue(int val, int low, int high)` "
        "to practice clicking line numbers, selecting a verdict, and submitting your confidence."
    ),
    "code": (
        "int clampValue(int val, int low, int high) {\n"
        "    if (low > high) {\n"
        "        return low;\n"
        "    }\n"
        "    if (val < low) {\n"
        "        return low;\n"
        "    }\n"
        "    if (val > high) {\n"
        "        return high;\n"
        "    }\n"
        "    return val;\n"
        "}"
    ),
    "ground_truth_correct": True,
    "ground_truth_error_line": None,
    "ground_truth_error_description": None,
    "explanation_notes": [
        {
            "line": 2,
            "title": "Range Guard",
            "text": "Returns `low` immediately if the caller passes an inverted range (`low > high`).",
        },
        {
            "line": 5,
            "title": "Lower & Upper Clamping",
            "text": "Clamps `val` to `[low, high]` and returns `val` unchanged if already in range.",
        },
    ],
    "verification_guided": {
        "assumptions": ["Assumes `low <= high` for normal clamping."],
        "suggested_edge_cases": ["val = 5, low = 1, high = 10", "val = -3, low = 0, high = 5"],
        "attention_lines": [2, 5, 8],
        "checklist": ["Check lower bound `<` comparison.", "Check upper bound `>` comparison."],
        "expandable_hints": [],
    },
}

VALIDATED_TASKS = [
    {
        "id": "core_rate_limiter",
        "title": "Sliding-Window API Rate Limiter",
        "difficulty": "Medium",
        "pair_group": "A",
        "task_set": "core",
        "problem_statement": (
            "Review this C++ `RateLimiter` class that allows at most `maxRequests` calls within any "
            "`windowSec`-second sliding window. `allowRequest(uint64_t nowSec)` returns `true` and records "
            "the call if under the limit, or `false` otherwise."
        ),
        "code": (
            "#include <cstdint>\n"
            "#include <deque>\n"
            "\n"
            "class RateLimiter {\n"
            "public:\n"
            "    RateLimiter(size_t maxRequests, uint64_t windowSec)\n"
            "        : maxRequests_(maxRequests), windowSec_(windowSec) {}\n"
            "\n"
            "    bool allowRequest(uint64_t nowSec) {\n"
            "        if (maxRequests_ == 0) {\n"
            "            return false;\n"
            "        }\n"
            "        uint64_t windowStart = nowSec - windowSec_;\n"
            "        while (!timestamps_.empty() && timestamps_.front() <= windowStart) {\n"
            "            timestamps_.pop_front();\n"
            "        }\n"
            "        if (timestamps_.size() >= maxRequests_) {\n"
            "            return false;\n"
            "        }\n"
            "        timestamps_.push_back(nowSec);\n"
            "        return true;\n"
            "    }\n"
            "\n"
            "    size_t currentWindowCount() const {\n"
            "        return timestamps_.size();\n"
            "    }\n"
            "\n"
            "private:\n"
            "    size_t maxRequests_;\n"
            "    uint64_t windowSec_;\n"
            "    std::deque<uint64_t> timestamps_;\n"
            "};"
        ),
        "ground_truth_correct": False,
        "ground_truth_error_line": 13,
        "ground_truth_error_description": (
            "`nowSec - windowSec_` uses unsigned `uint64_t` subtraction. When `nowSec < windowSec_` "
            "(e.g., `nowSec = 5`, `windowSec_ = 60`), `windowStart` underflows to `~1.84e19`, causing "
            "`timestamps_.front() <= windowStart` to be true for all entries and wiping the rate limiter."
        ),
        "explanation_notes": [
            {
                "line": 10,
                "title": "Zero-Limit Guard",
                "text": "Rejects all requests immediately if `maxRequests_` is configured as 0.",
            },
            {
                "line": 13,
                "title": "Window Cutoff Calculation",
                "text": "Computes the earliest valid timestamp `windowStart` as `nowSec - windowSec_`.",
            },
            {
                "line": 14,
                "title": "Expired Entry Eviction",
                "text": "Pops timestamps from the front of the deque while they are at or before `windowStart`.",
            },
            {
                "line": 17,
                "title": "Capacity Check & Record",
                "text": "Denies the request if `timestamps_.size() >= maxRequests_`; otherwise records `nowSec`.",
            },
        ],
        "verification_guided": {
            "assumptions": [
                "Assumes `allowRequest` is called with non-decreasing `nowSec` timestamps.",
                "Uses unsigned 64-bit integers (`uint64_t`) for timestamps and window duration.",
            ],
            "suggested_edge_cases": [
                "Early timestamps: windowSec_ = 60, calls at nowSec = 1, 2, 3",
                "Exact boundary: nowSec = 100, windowSec_ = 10, prior call at 90",
                "Zero capacity: maxRequests_ = 0",
            ],
            "attention_lines": [13, 14, 17],
            "checklist": [
                "Check unsigned arithmetic (`uint64_t`) for potential underflow.",
                "Verify eviction condition (`<=` vs `<`) at the window boundary.",
                "Confirm rejected requests are not pushed into `timestamps_`.",
            ],
            "expandable_hints": [
                {
                    "line": 13,
                    "label": "Inspect `nowSec - windowSec_`",
                    "detail": "What value does `uint64_t windowStart` hold when `nowSec = 5` and `windowSec_ = 60`?",
                },
            ],
        },
    },
    {
        "id": "core_interval_merger",
        "title": "Merge Overlapping Schedule Intervals",
        "difficulty": "Medium",
        "pair_group": "A",
        "task_set": "core",
        "problem_statement": (
            "Review this C++ function `mergeIntervals` that takes a list of `[start, end]` intervals "
            "(where `start <= end`), merges all overlapping or touching intervals (`next.start <= cur.end`), "
            "and returns the merged intervals sorted by start time."
        ),
        "code": (
            "#include <algorithm>\n"
            "#include <vector>\n"
            "\n"
            "struct Interval {\n"
            "    int start;\n"
            "    int end;\n"
            "};\n"
            "\n"
            "std::vector<Interval> mergeIntervals(std::vector<Interval> intervals) {\n"
            "    if (intervals.empty()) {\n"
            "        return {};\n"
            "    }\n"
            "    std::sort(intervals.begin(), intervals.end(),\n"
            "              [](const Interval& a, const Interval& b) {\n"
            "                  if (a.start != b.start) {\n"
            "                      return a.start < b.start;\n"
            "                  }\n"
            "                  return a.end < b.end;\n"
            "              });\n"
            "\n"
            "    std::vector<Interval> merged;\n"
            "    merged.push_back(intervals[0]);\n"
            "    for (size_t i = 1; i < intervals.size(); i++) {\n"
            "        Interval& last = merged.back();\n"
            "        const Interval& curr = intervals[i];\n"
            "        if (curr.start <= last.end) {\n"
            "            last.end = std::max(last.end, curr.end);\n"
            "        } else {\n"
            "            merged.push_back(curr);\n"
            "        }\n"
            "    }\n"
            "    return merged;\n"
            "}"
        ),
        "ground_truth_correct": True,
        "ground_truth_error_line": None,
        "ground_truth_error_description": None,
        "explanation_notes": [
            {
                "line": 10,
                "title": "Empty Input Guard",
                "text": "Returns an empty vector immediately so `intervals[0]` is never accessed out of bounds.",
            },
            {
                "line": 13,
                "title": "Lexicographic Sort",
                "text": "Sorts intervals by `start` ascending, breaking ties by `end` ascending.",
            },
            {
                "line": 26,
                "title": "Overlap Merge",
                "text": "Extends `last.end` with `std::max` when `curr.start <= last.end`; otherwise starts a new interval.",
            },
        ],
        "verification_guided": {
            "assumptions": [
                "Assumes each input interval satisfies `start <= end`.",
                "Treats touching endpoints (`[1, 3]` and `[3, 5]`) as overlapping.",
            ],
            "suggested_edge_cases": [
                "Empty vector: {}",
                "Nested interval: {[1, 10], [2, 5]} -> should stay [1, 10]",
                "Touching & same-start intervals: {[1, 4], [1, 2], [4, 6]}",
            ],
            "attention_lines": [10, 15, 26, 27],
            "checklist": [
                "Verify empty and single-element inputs do not crash.",
                "Check nested intervals where `curr.end < last.end`.",
                "Verify reference `Interval& last = merged.back()` stays valid (no push_back inside the `if` branch).",
            ],
            "expandable_hints": [
                {
                    "line": 27,
                    "label": "Check reference invalidation",
                    "detail": "`merged.push_back(curr)` only runs in the `else` branch, so `last` is never used after reallocation.",
                },
            ],
        },
    },
    {
        "id": "core_log_parser",
        "title": "HTTP Session Duration Tracker",
        "difficulty": "Medium",
        "pair_group": "B",
        "task_set": "core",
        "problem_statement": (
            "Review this C++ function `computeSessionDurations` that processes chronological `(eventType, timestamp)` "
            "records for a single user. `'START'` begins a session (ignoring duplicate `'START'`s if already active), "
            "`'END'` closes the active session, and if the log ends while a session is still open, it should be "
            "closed at `streamEndTime`."
        ),
        "code": (
            "#include <string>\n"
            "#include <vector>\n"
            "\n"
            "struct LogEvent {\n"
            "    std::string type;  // \"START\" or \"END\"\n"
            "    int timestamp;\n"
            "};\n"
            "\n"
            "std::vector<int> computeSessionDurations(const std::vector<LogEvent>& events,\n"
            "                                         int streamEndTime) {\n"
            "    std::vector<int> durations;\n"
            "    bool inSession = false;\n"
            "    int sessionStart = 0;\n"
            "\n"
            "    for (const auto& ev : events) {\n"
            "        if (ev.type == \"START\") {\n"
            "            if (!inSession) {\n"
            "                inSession = true;\n"
            "                sessionStart = ev.timestamp;\n"
            "            }\n"
            "        } else if (ev.type == \"END\") {\n"
            "            if (inSession) {\n"
            "                int dur = ev.timestamp - sessionStart;\n"
            "                if (dur >= 0) {\n"
            "                    durations.push_back(dur);\n"
            "                }\n"
            "                inSession = false;\n"
            "            }\n"
            "        }\n"
            "    }\n"
            "    return durations;\n"
            "}"
        ),
        "ground_truth_correct": False,
        "ground_truth_error_line": 31,
        "ground_truth_error_description": (
            "Missing post-loop flush: if `inSession` is still `true` after the `for` loop finishes, "
            "the open session is never closed at `streamEndTime` and its duration is silently dropped."
        ),
        "explanation_notes": [
            {
                "line": 12,
                "title": "Session State Machine",
                "text": "Tracks whether a session is currently open (`inSession`) and when it began (`sessionStart`).",
            },
            {
                "line": 17,
                "title": "Idempotent START",
                "text": "Ignores nested `START` events when `inSession` is already true.",
            },
            {
                "line": 22,
                "title": "Session Close",
                "text": "On `END`, computes non-negative duration and resets `inSession` to false.",
            },
        ],
        "verification_guided": {
            "assumptions": [
                "Assumes `events` are sorted chronologically and `streamEndTime >= last event timestamp`.",
                "Unpaired `END` events (when `inSession == false`) are ignored.",
            ],
            "suggested_edge_cases": [
                "Unclosed session: {(\"START\", 10)} with streamEndTime = 25",
                "Duplicate START: {(\"START\", 5), (\"START\", 8), (\"END\", 12)}",
                "Orphan END: {(\"END\", 5), (\"START\", 10), (\"END\", 15)}",
            ],
            "attention_lines": [10, 22, 31],
            "checklist": [
                "Check whether `streamEndTime` parameter is actually used.",
                "Trace what happens if the log ends while `inSession == true`.",
                "Verify duplicate `START` and orphan `END` handling.",
            ],
            "expandable_hints": [
                {
                    "line": 31,
                    "label": "Check post-loop state",
                    "detail": "Notice `streamEndTime` is accepted as a parameter on line 10—trace if it is ever referenced before `return durations;`.",
                },
            ],
        },
    },
    {
        "id": "core_lru_counter",
        "title": "Bounded LRU Key-Value Cache",
        "difficulty": "Hard",
        "pair_group": "B",
        "task_set": "core",
        "problem_statement": (
            "Review this C++ `LRUCache` supporting `get(int key)` (returns value or `-1`) and "
            "`put(int key, int value)` with O(1) average time and strict `capacity` eviction of the "
            "least-recently-used key."
        ),
        "code": (
            "#include <list>\n"
            "#include <unordered_map>\n"
            "#include <utility>\n"
            "\n"
            "class LRUCache {\n"
            "public:\n"
            "    explicit LRUCache(size_t capacity) : capacity_(capacity) {}\n"
            "\n"
            "    int get(int key) {\n"
            "        auto it = index_.find(key);\n"
            "        if (it == index_.end()) {\n"
            "            return -1;\n"
            "        }\n"
            "        items_.splice(items_.begin(), items_, it->second);\n"
            "        return it->second->second;\n"
            "    }\n"
            "\n"
            "    void put(int key, int value) {\n"
            "        if (capacity_ == 0) {\n"
            "            return;\n"
            "        }\n"
            "        auto it = index_.find(key);\n"
            "        if (it != index_.end()) {\n"
            "            it->second->second = value;\n"
            "            items_.splice(items_.begin(), items_, it->second);\n"
            "            return;\n"
            "        }\n"
            "        if (items_.size() == capacity_) {\n"
            "            int lruKey = items_.back().first;\n"
            "            index_.erase(lruKey);\n"
            "            items_.pop_back();\n"
            "        }\n"
            "        items_.emplace_front(key, value);\n"
            "        index_[key] = items_.begin();\n"
            "    }\n"
            "\n"
            "private:\n"
            "    size_t capacity_;\n"
            "    std::list<std::pair<int, int>> items_;\n"
            "    std::unordered_map<int, std::list<std::pair<int, int>>::iterator> index_;\n"
            "};"
        ),
        "ground_truth_correct": True,
        "ground_truth_error_line": None,
        "ground_truth_error_description": None,
        "explanation_notes": [
            {
                "line": 14,
                "title": "O(1) Recency Promotion",
                "text": "`items_.splice` moves the accessed node to the front of `items_` without invalidating list iterators.",
            },
            {
                "line": 19,
                "title": "Zero-Capacity Guard",
                "text": "Returns early in `put` when `capacity_ == 0` so `items_.back()` is never called on an empty list.",
            },
            {
                "line": 28,
                "title": "LRU Eviction",
                "text": "Removes the tail key from `index_` and `items_` when at full capacity before inserting the new key.",
            },
        ],
        "verification_guided": {
            "assumptions": [
                "`std::list::splice` preserves iterator validity for all elements.",
                "`capacity_ == 0` should safely store nothing.",
            ],
            "suggested_edge_cases": [
                "capacity = 0: put(1, 10), get(1) -> -1",
                "Update existing key at full capacity: put(1,1), put(2,2), put(1,9), put(3,3)",
                "get() promotes key so it is not evicted next",
            ],
            "attention_lines": [14, 19, 23, 28],
            "checklist": [
                "Check if updating an existing key at full capacity triggers a false eviction.",
                "Verify `capacity_ == 0` does not call `items_.back()`.",
                "Confirm `index_` and `items_` stay in sync during eviction.",
            ],
            "expandable_hints": [
                {
                    "line": 23,
                    "label": "Trace update at full capacity",
                    "detail": "Because `if (it != index_.end())` returns early on line 26, `items_.size() == capacity_` is only checked for genuinely new keys.",
                },
            ],
        },
    },
    {
        "id": "core_ledger_validator",
        "title": "Batch Bank Ledger Transfer Validator",
        "difficulty": "Medium",
        "pair_group": "C",
        "task_set": "core",
        "problem_statement": (
            "Review this C++ function `validateBatchTransfers` that checks whether a batch of transfers "
            "can execute atomically without any account going negative. Every transfer must have `amount > 0`, "
            "`from != to`, both accounts must exist, and no account may drop below 0 at any point in the batch."
        ),
        "code": (
            "#include <string>\n"
            "#include <unordered_map>\n"
            "#include <vector>\n"
            "\n"
            "struct Transfer {\n"
            "    std::string from;\n"
            "    std::string to;\n"
            "    long long amount;\n"
            "};\n"
            "\n"
            "bool validateBatchTransfers(const std::unordered_map<std::string, long long>& balances,\n"
            "                            const std::vector<Transfer>& batch) {\n"
            "    for (const auto& tx : batch) {\n"
            "        if (tx.amount <= 0 || tx.from == tx.to) {\n"
            "            return false;\n"
            "        }\n"
            "        auto fromIt = balances.find(tx.from);\n"
            "        auto toIt = balances.find(tx.to);\n"
            "        if (fromIt == balances.end() || toIt == balances.end()) {\n"
            "            return false;\n"
            "        }\n"
            "        if (fromIt->second < tx.amount) {\n"
            "            return false;\n"
            "        }\n"
            "    }\n"
            "    return true;\n"
            "}"
        ),
        "ground_truth_correct": False,
        "ground_truth_error_line": 22,
        "ground_truth_error_description": (
            "Each transfer is checked against the read-only `balances` map (`fromIt->second < tx.amount`) "
            "without tracking cumulative debits/credits across the batch. Two $60 transfers from an account "
            "with $100 both pass individually, causing a -$20 overdraft."
        ),
        "explanation_notes": [
            {
                "line": 14,
                "title": "Transfer Sanity Check",
                "text": "Rejects non-positive transfer amounts and self-transfers (`from == to`).",
            },
            {
                "line": 17,
                "title": "Account Existence Check",
                "text": "Verifies both sender and receiver keys exist in `balances`.",
            },
            {
                "line": 22,
                "title": "Balance Sufficiency Check",
                "text": "Compares `tx.amount` against `fromIt->second` in the `balances` map.",
            },
        ],
        "verification_guided": {
            "assumptions": [
                "Assumes `balances` contains non-negative starting balances.",
                "Transfers in `batch` are applied sequentially in order.",
            ],
            "suggested_edge_cases": [
                "Multiple debits from same account: A=$100, batch=[A->B $60, A->C $60]",
                "Chained credit then debit: A=$0, B=$50, batch=[B->A $50, A->C $50]",
                "Self-transfer or zero amount: A->A $10",
            ],
            "attention_lines": [11, 22],
            "checklist": [
                "Check if `balances` is mutated or copied into a working map.",
                "Trace two consecutive debits from the same account in one batch.",
                "Trace a credit followed by a debit on the same account.",
            ],
            "expandable_hints": [
                {
                    "line": 22,
                    "label": "Trace cumulative batch state",
                    "detail": "`balances` is `const` and never updated between iterations, so `fromIt->second` always reflects the initial balance.",
                },
            ],
        },
    },
    {
        "id": "core_grid_robot",
        "title": "2D Grid Robot Command Simulator",
        "difficulty": "Medium",
        "pair_group": "C",
        "task_set": "core",
        "problem_statement": (
            "Review this C++ function `simulateRobot` on a `rows x cols` grid where `grid[r][c] == 1` is an obstacle. "
            "Starting at `(0, 0)` facing North (`0`), commands `'L'`/`'R'` turn 90 degrees and `'F'` steps forward "
            "only if the target cell is inside bounds and not an obstacle."
        ),
        "code": (
            "#include <string>\n"
            "#include <utility>\n"
            "#include <vector>\n"
            "\n"
            "std::pair<int, int> simulateRobot(const std::vector<std::vector<int>>& grid,\n"
            "                                  const std::string& commands) {\n"
            "    if (grid.empty() || grid[0].empty() || grid[0][0] == 1) {\n"
            "        return {0, 0};\n"
            "    }\n"
            "    const int rows = static_cast<int>(grid.size());\n"
            "    const int cols = static_cast<int>(grid[0].size());\n"
            "    // Directions: 0=North(-1,0), 1=East(0,+1), 2=South(+1,0), 3=West(0,-1)\n"
            "    const int dr[4] = {-1, 0, 1, 0};\n"
            "    const int dc[4] = {0, 1, 0, -1};\n"
            "\n"
            "    int r = 0, c = 0, dir = 0;\n"
            "    for (char cmd : commands) {\n"
            "        if (cmd == 'R') {\n"
            "            dir = (dir + 1) % 4;\n"
            "        } else if (cmd == 'L') {\n"
            "            dir = (dir + 3) % 4;\n"
            "        } else if (cmd == 'F') {\n"
            "            int nr = r + dr[dir];\n"
            "            int nc = c + dc[dir];\n"
            "            if (nr >= 0 && nr < rows && nc >= 0 && nc < cols && grid[nr][nc] == 0) {\n"
            "                r = nr;\n"
            "                c = nc;\n"
            "            }\n"
            "        }\n"
            "    }\n"
            "    return {r, c};\n"
            "}"
        ),
        "ground_truth_correct": True,
        "ground_truth_error_line": None,
        "ground_truth_error_description": None,
        "explanation_notes": [
            {
                "line": 7,
                "title": "Grid & Origin Guard",
                "text": "Handles empty grids or a blocked `(0, 0)` start cell safely.",
            },
            {
                "line": 20,
                "title": "Safe Left Turn Modulo",
                "text": "Uses `(dir + 3) % 4` instead of `(dir - 1) % 4` to avoid negative modulo results in C++.",
            },
            {
                "line": 25,
                "title": "Bounds Before Obstacle Access",
                "text": "Short-circuits `nr/nc` bounds checks before indexing `grid[nr][nc]`.",
            },
        ],
        "verification_guided": {
            "assumptions": [
                "`grid` is rectangular (`grid[0].size()` applies to all rows).",
                "Row 0 is North, so moving North decreases `r` by 1.",
            ],
            "suggested_edge_cases": [
                "Turn left from North (dir=0): should become West (dir=3)",
                "Step North from (0, 0): nr = -1 must be blocked by bounds check",
                "Obstacle directly in front of robot",
            ],
            "attention_lines": [7, 13, 21, 25],
            "checklist": [
                "Verify `(dir + 3) % 4` wraps North -> West cleanly.",
                "Check bounds conditions (`nr < rows` vs `<=`).",
                "Confirm `grid[nr][nc]` is only accessed after bounds validation.",
            ],
            "expandable_hints": [
                {
                    "line": 21,
                    "label": "Check C++ negative modulo",
                    "detail": "In C++, `-1 % 4` evaluates to `-1`, so adding `+ 3` before `% 4` is required for safe counter-clockwise turns.",
                },
            ],
        },
    },
]

# ==================== PHASE 2: SYSTEMS & 100+ LINE COMPLEX TASKS ====================

SYSTEMS_COMPLEX_TASKS = [
    {
        "id": "sys_ring_buffer",
        "title": "Systems: Bounded Ring Buffer (Circular Queue)",
        "difficulty": "Hard",
        "pair_group": "S",
        "task_set": "systems_challenge",
        "problem_statement": (
            "Implement a fixed-capacity C++ `RingBuffer` for a kernel/driver packet queue supporting "
            "`push`, `pop`, `isEmpty`, `isFull`, and `size` without dynamic allocations after construction."
        ),
        "code": (
            "#include <vector>\n"
            "#include <cstddef>\n"
            "\n"
            "class RingBuffer {\n"
            "public:\n"
            "    explicit RingBuffer(size_t capacity)\n"
            "        : buffer_(capacity), head_(0), tail_(0), count_(0) {}\n"
            "\n"
            "    bool isEmpty() const { return count_ == 0; }\n"
            "    bool isFull() const { return count_ == buffer_.size(); }\n"
            "    size_t size() const { return count_; }\n"
            "\n"
            "    bool push(int value) {\n"
            "        if (isFull() || buffer_.empty()) {\n"
            "            return false;\n"
            "        }\n"
            "        buffer_[tail_] = value;\n"
            "        tail_ = (tail_ + 1) % buffer_.size();\n"
            "        count_++;\n"
            "        return true;\n"
            "    }\n"
            "\n"
            "    bool pop(int& outValue) {\n"
            "        if (isEmpty()) {\n"
            "            return false;\n"
            "        }\n"
            "        outValue = buffer_[head_];\n"
            "        head_ = (head_ + 1) % buffer_.size();\n"
            "        count_--;\n"
            "        return true;\n"
            "    }\n"
            "\n"
            "private:\n"
            "    std::vector<int> buffer_;\n"
            "    size_t head_;\n"
            "    size_t tail_;\n"
            "    size_t count_;\n"
            "};"
        ),
        "ground_truth_correct": True,
        "ground_truth_error_line": None,
        "ground_truth_error_description": None,
        "explanation_notes": [
            {
                "line": 10,
                "title": "Explicit Occupancy Counter",
                "text": "Tracks `count_` separately from `head_` and `tail_` so full vs. empty states are unambiguous.",
            },
            {
                "line": 14,
                "title": "Zero-Capacity & Full Guard",
                "text": "Rejects `push` if `isFull()` or `buffer_.empty()`, preventing modulo-by-zero on line 18.",
            },
            {
                "line": 28,
                "title": "Wrap-Around Indexing",
                "text": "Advances `head_` and `tail_` modulo `buffer_.size()` in FIFO order.",
            },
        ],
        "verification_guided": {
            "assumptions": [
                "Single-threaded caller (no internal mutex).",
                "Zero-capacity buffer (`capacity = 0`) must safely return `false` on push/pop.",
            ],
            "suggested_edge_cases": [
                "capacity = 0: push(10) -> must not divide by zero",
                "Wrap-around: push 3, pop 2, push 2 on capacity 3",
                "Pop on empty buffer -> returns false without modifying outValue",
            ],
            "attention_lines": [14, 18, 28],
            "checklist": [
                "Check for modulo-by-zero when `capacity == 0`.",
                "Verify `head_` and `tail_` wrap cleanly without overwriting unread items.",
                "Confirm `count_` stays synchronized with `push` and `pop`.",
            ],
            "expandable_hints": [
                {
                    "line": 14,
                    "label": "Check capacity=0 guard",
                    "detail": "When `capacity == 0`, `count_ == buffer_.size()` (0 == 0) is true and `buffer_.empty()` is true, so `push` returns `false` before `% buffer_.size()`.",
                },
            ],
        },
    },
    {
        "id": "sys_packet_parser",
        "title": "Systems: Network Packet Frame Parser",
        "difficulty": "Hard",
        "pair_group": "S",
        "task_set": "systems_challenge",
        "problem_statement": (
            "Write a C++ function `bool extractPayload(...)` that reads a 2-byte big-endian payload length "
            "at `offset` from a raw byte buffer `frame` and copies `payloadLen` bytes into `outPayload`."
        ),
        "code": (
            "#include <cstdint>\n"
            "#include <cstddef>\n"
            "#include <vector>\n"
            "\n"
            "bool extractPayload(const std::vector<uint8_t>& frame,\n"
            "                    size_t offset,\n"
            "                    std::vector<uint8_t>& outPayload) {\n"
            "    if (offset + 2 > frame.size()) {\n"
            "        return false;\n"
            "    }\n"
            "    uint16_t payloadLen = (static_cast<uint16_t>(frame[offset]) << 8) |\n"
            "                          static_cast<uint16_t>(frame[offset + 1]);\n"
            "    uint16_t endPos = static_cast<uint16_t>(offset + 2 + payloadLen);\n"
            "    if (endPos > frame.size()) {\n"
            "        return false;\n"
            "    }\n"
            "    outPayload.assign(frame.begin() + offset + 2,\n"
            "                      frame.begin() + offset + 2 + payloadLen);\n"
            "    return true;\n"
            "}"
        ),
        "ground_truth_correct": False,
        "ground_truth_error_line": 13,
        "ground_truth_error_description": (
            "`endPos` is stored in a `uint16_t`, so `offset + 2 + payloadLen` can wrap around modulo 65536 "
            "(e.g., if `payloadLen = 65535` and `offset = 4`, `endPos` wraps to `5`, bypassing `endPos > frame.size()` and causing an out-of-bounds read on line 18)."
        ),
        "explanation_notes": [
            {
                "line": 8,
                "title": "Header Bounds Check",
                "text": "Ensures at least 2 header bytes exist starting at `offset`.",
            },
            {
                "line": 11,
                "title": "Big-Endian Length Decode",
                "text": "Combines two bytes into a 16-bit unsigned `payloadLen`.",
            },
            {
                "line": 13,
                "title": "Payload End Calculation",
                "text": "Computes `endPos` as `uint16_t` and compares it against `frame.size()`.",
            },
        ],
        "verification_guided": {
            "assumptions": [
                "Assumes `frame` is an untrusted network buffer of arbitrary size.",
                "Assumes `offset` is small relative to `SIZE_MAX`.",
            ],
            "suggested_edge_cases": [
                "Malicious `payloadLen = 65535` on a 10-byte `frame`",
                "Zero-length payload (`payloadLen = 0`) at the end of `frame`",
                "`offset` near `frame.size()` (e.g., `offset = frame.size() - 1`)",
            ],
            "attention_lines": [8, 13, 14, 18],
            "checklist": [
                "Check integer width used in `endPos` bounds calculation.",
                "Test whether `offset + 2 + payloadLen` can overflow `uint16_t`.",
                "Verify `outPayload.assign(...)` uses safe iterators.",
            ],
            "expandable_hints": [
                {
                    "line": 13,
                    "label": "Check `uint16_t` wrap-around",
                    "detail": "A 16-bit unsigned integer holds 0..65535; adding `offset + 2 + payloadLen` can wrap past 65535 to a small value.",
                },
            ],
        },
    },
    {
        "id": "sys_slab_allocator_100",
        "title": "Complex Systems (108 Lines): Fixed-Block Page & Slab Allocator",
        "difficulty": "Hard",
        "pair_group": "S",
        "task_set": "systems_challenge",
        "problem_statement": (
            "Review this 108-line C++ `SlabAllocator` modeled after a kernel fixed-size object cache. "
            "It manages fixed-size slots across multiple memory pages, tracks allocation bitmaps, "
            "supports `allocate()`, `deallocate()`, and `ownsAddress()`, and reports utilization stats."
        ),
        "code": (
            "#include <cstdint>\n"
            "#include <cstddef>\n"
            "#include <vector>\n"
            "#include <cstring>\n"
            "#include <stdexcept>\n"
            "\n"
            "struct SlabPage {\n"
            "    uint8_t* memory;\n"
            "    std::vector<bool> used;\n"
            "    size_t freeCount;\n"
            "\n"
            "    SlabPage(size_t slotSize, size_t slotsPerPage)\n"
            "        : memory(new uint8_t[slotSize * slotsPerPage]),\n"
            "          used(slotsPerPage, false),\n"
            "          freeCount(slotsPerPage) {\n"
            "        std::memset(memory, 0, slotSize * slotsPerPage);\n"
            "    }\n"
            "\n"
            "    ~SlabPage() {\n"
            "        delete[] memory;\n"
            "    }\n"
            "\n"
            "    SlabPage(const SlabPage&) = delete;\n"
            "    SlabPage& operator=(const SlabPage&) = delete;\n"
            "\n"
            "    SlabPage(SlabPage&& other) noexcept\n"
            "        : memory(other.memory),\n"
            "          used(std::move(other.used)),\n"
            "          freeCount(other.freeCount) {\n"
            "        other.memory = nullptr;\n"
            "        other.freeCount = 0;\n"
            "    }\n"
            "};\n"
            "\n"
            "class SlabAllocator {\n"
            "public:\n"
            "    SlabAllocator(size_t slotSize, size_t slotsPerPage)\n"
            "        : slotSize_(slotSize),\n"
            "          slotsPerPage_(slotsPerPage),\n"
            "          totalAllocated_(0) {\n"
            "        if (slotSize_ == 0 || slotsPerPage_ == 0) {\n"
            "            throw std::invalid_argument(\"Slot size and count must be > 0\");\n"
            "        }\n"
            "        pages_.emplace_back(slotSize_, slotsPerPage_);\n"
            "    }\n"
            "\n"
            "    void* allocate() {\n"
            "        for (auto& page : pages_) {\n"
            "            if (page.freeCount == 0) {\n"
            "                continue;\n"
            "            }\n"
            "            for (size_t i = 0; i < slotsPerPage_; i++) {\n"
            "                if (!page.used[i]) {\n"
            "                    page.used[i] = true;\n"
            "                    page.freeCount--;\n"
            "                    totalAllocated_++;\n"
            "                    return page.memory + (i * slotSize_);\n"
            "                }\n"
            "            }\n"
            "        }\n"
            "        pages_.emplace_back(slotSize_, slotsPerPage_);\n"
            "        SlabPage& newPage = pages_.back();\n"
            "        newPage.used[0] = true;\n"
            "        newPage.freeCount--;\n"
            "        totalAllocated_++;\n"
            "        return newPage.memory;\n"
            "    }\n"
            "\n"
            "    bool deallocate(void* ptr) {\n"
            "        if (ptr == nullptr) {\n"
            "            return false;\n"
            "        }\n"
            "        const uint8_t* bytePtr = static_cast<const uint8_t*>(ptr);\n"
            "        for (auto& page : pages_) {\n"
            "            const uint8_t* start = page.memory;\n"
            "            const uint8_t* end = start + (slotSize_ * slotsPerPage_);\n"
            "            if (bytePtr >= start && bytePtr < end) {\n"
            "                size_t offset = static_cast<size_t>(bytePtr - start);\n"
            "                if (offset % slotSize_ != 0) {\n"
            "                    return false;\n"
            "                }\n"
            "                size_t idx = offset / slotSize_;\n"
            "                if (!page.used[idx]) {\n"
            "                    return false;\n"
            "                }\n"
            "                page.used[idx] = false;\n"
            "                page.freeCount++;\n"
            "                totalAllocated_--;\n"
            "                return true;\n"
            "            }\n"
            "        }\n"
            "        return false;\n"
            "    }\n"
            "\n"
            "    bool ownsAddress(const void* ptr) const {\n"
            "        const uint8_t* bytePtr = static_cast<const uint8_t*>(ptr);\n"
            "        for (const auto& page : pages_) {\n"
            "            const uint8_t* start = page.memory;\n"
            "            const uint8_t* end = start + (slotSize_ * slotsPerPage_);\n"
            "            if (bytePtr >= start && bytePtr < end) {\n"
            "                return true;\n"
            "            }\n"
            "        }\n"
            "        return false;\n"
            "    }\n"
            "\n"
            "    size_t pageCount() const { return pages_.size(); }\n"
            "    size_t activeAllocations() const { return totalAllocated_; }\n"
            "\n"
            "private:\n"
            "    size_t slotSize_;\n"
            "    size_t slotsPerPage_;\n"
            "    size_t totalAllocated_;\n"
            "    std::vector<SlabPage> pages_;\n"
            "};"
        ),
        "ground_truth_correct": True,
        "ground_truth_error_line": None,
        "ground_truth_error_description": None,
        "explanation_notes": [
            {
                "line": 26,
                "title": "Noexcept Move Constructor",
                "text": "Transfers raw `memory` ownership and nulls `other.memory` so `std::vector<SlabPage>` growth is safe.",
            },
            {
                "line": 47,
                "title": "First-Fit & Page Growth",
                "text": "Scans existing pages for `freeCount > 0`, or appends a new `SlabPage` when all pages are full.",
            },
            {
                "line": 70,
                "title": "Pointer Validation in Deallocate",
                "text": "Checks `ptr != nullptr`, address range `[start, end)`, slot alignment (`offset % slotSize_ == 0`), and double-free.",
            },
        ],
        "verification_guided": {
            "assumptions": [
                "Assumes `slotSize_` and `slotsPerPage_` are strictly positive.",
                "Assumes `deallocate` only frees aligned slot start addresses.",
            ],
            "suggested_edge_cases": [
                "Allocate more than `slotsPerPage_` items to trigger a second `SlabPage`",
                "Call `deallocate(ptr + 1)` with an unaligned interior pointer",
                "Call `deallocate(ptr)` twice on the same pointer (double-free)",
            ],
            "attention_lines": [26, 61, 79, 83],
            "checklist": [
                "Check `SlabPage` move semantics when `pages_` reallocates.",
                "Check alignment and double-free guards in `deallocate`.",
                "Verify `totalAllocated_` and `freeCount` stay consistent across page growth.",
            ],
            "expandable_hints": [
                {
                    "line": 26,
                    "label": "Check `SlabPage` move safety",
                    "detail": "Because `SlabPage(SlabPage&&)` is `noexcept` and sets `other.memory = nullptr`, `delete[] nullptr` on the moved-from object is a safe no-op.",
                },
            ],
        },
    },
]
