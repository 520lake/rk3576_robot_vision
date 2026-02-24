# SERIAL COMMUNICATION PROTOCOL
## Target Device: Arduino Controller (Uno R4 Minima / Compatible)

This document defines the serial communication protocol between the Brain (Python/RK3576) and the Controller (Arduino).

### Connection Settings
- **Baud Rate**: 115200
- **Data Bits**: 8
- **Parity**: None
- **Stop Bits**: 1
- **Line Ending**: `\n` (Newline character)

### Command Format
All commands are ASCII strings terminated by a newline character.
Format: `Command:Argument1,Argument2`

---

### 1. Movement Control (Visual Tracking)
Control the pan/tilt servos to track an object.

**Command:** `Move:x_offset,y_offset`

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `x_offset` | `int` | Relative movement for X-axis (Pan). Positive = Right, Negative = Left. |
| `y_offset` | `int` | Relative movement for Y-axis (Tilt). Positive = Down, Negative = Up. |

**Example:**
- `Move:10,-5` (Move right 10 degrees, up 5 degrees)
- `Move:0,0` (No movement)

---

### 2. Emoji Control (OLED Display)
Display different facial expressions on the OLED screen.

**Command:** `Emoji:name`

| Parameter | Type | Description | Supported Values |
| :--- | :--- | :--- | :--- |
| `name` | `string` | Name of the emoji to display | `happy`, `sad`, `anger`, `surprise`, `blink`, `sleep`, `wakeup`, `right`, `left`, `center` |

**Example:**
- `Emoji:happy` (Show happy eyes)
- `Emoji:sleep` (Show sleeping line)

---

### 3. Action Control (Head Movements)
Perform predefined head gestures or movements.

**Command:** `Action:name`

| Parameter | Type | Description | Supported Values |
| :--- | :--- | :--- | :--- |
| `name` | `string` | Name of the action to perform | `nod`, `shake`, `roll_left`, `roll_right`, `random` |

**Example:**
- `Action:nod` (Nod head up and down)
- `Action:shake` (Shake head left and right)
- `Action:random` (Perform a random idle action)

---

### 4. Idle Behavior
The robot automatically enters **Idle Mode** if no commands are received for **5 seconds**.
In Idle Mode, the robot will randomly:
- Blink eyes
- Look around slightly
- Perform random head movements

Sending *any* command will immediately wake the robot from Idle Mode.
