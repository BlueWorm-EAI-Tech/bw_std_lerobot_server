# Dataset Gap Analysis Report
## Dataset: /home/lcjs-szw/datasets/pick_place_cube

**Analysis Date:** January 17, 2026  
**Total Episodes:** 109  
**Total Frames:** 231,763  
**Number of Joints:** 16

---

## Executive Summary

The analysis calculated the gap between `action` and `observation.state` for each joint across all frames in the dataset. The gap is defined as: `gap = action - observation.state`

### Key Findings:

✅ **Most joints are well-behaved** with small gaps (< 0.01 average absolute gap)

⚠️ **6 problematic joints identified** with either high average gaps, high variability, or large spikes

---

## Problematic Joints

### 🔴 Joint 1: left_shoulder_roll_joint.pos
- **Issue:** High average absolute gap (0.092501)
- **Mean gap:** -0.092430 (strong negative bias)
- **Std dev:** 0.151826
- **Max absolute gap:** 0.683681
- **Outliers:** 45 frames (0.02%)
- **Analysis:** This joint shows a consistent negative bias, meaning actions are systematically lower than the current state. This could indicate a calibration issue or intentional offset.

### 🔴 Joint 9: right_shoulder_roll_joint.pos
- **Issue:** High average absolute gap (0.068085)
- **Mean gap:** -0.068085 (strong negative bias)
- **Std dev:** 0.136528
- **Max absolute gap:** 0.830493
- **Outliers:** 358 frames (0.15%)
- **Analysis:** Similar to joint 1, this shows systematic negative bias. Both shoulder roll joints exhibit this pattern.

### 🔴 Joint 0: left_shoulder_pitch_joint.pos
- **Issue:** Large spike detected (max gap: 0.588987)
- **Mean gap:** -0.000185 (well-centered)
- **Std dev:** 0.020471
- **Outliers:** 1,397 frames (0.60%)
- **Analysis:** Generally well-behaved but has occasional large spikes. Example shows state jumping from 0.103 to 0.560 while action stays at 0.032.

### 🔴 Joint 8: right_shoulder_pitch_joint.pos
- **Issue:** Large spike detected (max gap: 0.922749)
- **Mean gap:** 0.000002 (well-centered)
- **Std dev:** 0.027489
- **Outliers:** 1,406 frames (0.61%)
- **Analysis:** Similar to joint 0, mostly good but with occasional large deviations.

### 🔴 Joint 13: right_wrist_pitch_joint.pos
- **Issue:** Large spike detected (max gap: 0.750801)
- **Mean gap:** -0.010823 (slight negative bias)
- **Std dev:** 0.024806
- **Outliers:** 733 frames (0.32%)
- **Analysis:** Shows both systematic bias and occasional spikes.

### 🔴 Joint 14: right_wrist_yaw_joint.pos
- **Issue:** Large spike detected (max gap: 0.820307)
- **Mean gap:** -0.000001 (well-centered)
- **Std dev:** 0.016821
- **Outliers:** 1,037 frames (0.45%)
- **Analysis:** Well-centered on average but has significant outliers.

---

## Systematic Bias Analysis

Four joints show consistent directional bias (|mean| > 0.01):

| Joint | Name | Mean Gap | Direction |
|-------|------|----------|-----------|
| 1 | left_shoulder_roll_joint.pos | -0.092430 | Negative |
| 5 | left_wrist_pitch_joint.pos | -0.032987 | Negative |
| 9 | right_shoulder_roll_joint.pos | -0.068085 | Negative |
| 13 | right_wrist_pitch_joint.pos | -0.010823 | Negative |

**Interpretation:** All biased joints show negative bias, meaning actions are consistently lower than states. This could indicate:
1. A lag in the control system
2. Intentional damping/smoothing in the action space
3. Calibration offsets between state sensors and action commands

---

## Well-Behaved Joints

The following joints show excellent behavior with minimal gaps:

| Joint | Name | Abs Mean Gap |
|-------|------|--------------|
| 3 | left_elbow_joint.pos | 0.001657 |
| 11 | right_elbow_joint.pos | 0.001390 |
| 12 | right_wrist_roll_joint.pos | 0.001860 |
| 4 | left_wrist_roll_joint.pos | 0.002547 |
| 14 | right_wrist_yaw_joint.pos | 0.003552 |
| 6 | left_wrist_yaw_joint.pos | 0.003683 |

---

## Episode Consistency

### Episodes with Highest Average Gaps:
- Episode 75: 0.037603 mean absolute gap
- Episode 3: 0.033936 mean absolute gap
- Episode 19: 0.023974 mean absolute gap

### Episodes with Lowest Average Gaps:
- Episode 76: 0.013560 mean absolute gap
- Episode 67: 0.013661 mean absolute gap
- Episode 72: 0.013909 mean absolute gap

**Observation:** There's about 2.7x variation between best and worst episodes, suggesting some episodes may have had different recording conditions or robot behavior.

---

## Recommendations

1. **Shoulder Roll Joints (1, 9):** Investigate the systematic negative bias. Consider:
   - Checking calibration between state sensors and action commands
   - Verifying if this is intentional damping behavior
   - Reviewing if gravity compensation is properly configured

2. **Spike Detection (0, 8, 13, 14):** The large spikes appear to be transient events. Consider:
   - Filtering outliers during training (> 3σ)
   - Investigating if spikes occur at episode boundaries or specific events
   - Checking if these correspond to rapid movements or collisions

3. **Wrist Pitch Joints (5, 13):** Moderate negative bias suggests possible:
   - Gravity effects not fully compensated
   - Systematic lag in wrist control

4. **Data Quality:** Overall, 99%+ of frames are within 3σ, indicating good data quality despite the identified issues.

---

## Statistical Summary Table

| Joint | Name | Mean | Std | \|Mean\| | Max\|Gap\| | Status |
|-------|------|------|-----|----------|------------|--------|
| 0 | left_shoulder_pitch_joint.pos | -0.000185 | 0.020471 | 0.005839 | 0.588987 | ⚠️ SPIKE |
| 1 | left_shoulder_roll_joint.pos | -0.092430 | 0.151826 | 0.092501 | 0.683681 | ⚠️ HIGH |
| 2 | left_shoulder_yaw_joint.pos | -0.000293 | 0.012146 | 0.005644 | 0.370479 | ✅ OK |
| 3 | left_elbow_joint.pos | 0.000237 | 0.004900 | 0.001657 | 0.118538 | ✅ OK |
| 4 | left_wrist_roll_joint.pos | -0.000128 | 0.008050 | 0.002547 | 0.216951 | ✅ OK |
| 5 | left_wrist_pitch_joint.pos | -0.032987 | 0.027707 | 0.036328 | 0.470877 | ⚠️ BIAS |
| 6 | left_wrist_yaw_joint.pos | 0.000204 | 0.012390 | 0.003683 | 0.488420 | ✅ OK |
| 7 | left_gripper_joint.pos | 0.000838 | 0.019135 | 0.009411 | 0.319567 | ✅ OK |
| 8 | right_shoulder_pitch_joint.pos | 0.000002 | 0.027489 | 0.005084 | 0.922749 | ⚠️ SPIKE |
| 9 | right_shoulder_roll_joint.pos | -0.068085 | 0.136528 | 0.068085 | 0.830493 | ⚠️ HIGH |
| 10 | right_shoulder_yaw_joint.pos | -0.000383 | 0.015783 | 0.004695 | 0.439586 | ✅ OK |
| 11 | right_elbow_joint.pos | -0.000264 | 0.005825 | 0.001390 | 0.140930 | ✅ OK |
| 12 | right_wrist_roll_joint.pos | -0.000213 | 0.005836 | 0.001860 | 0.169683 | ✅ OK |
| 13 | right_wrist_pitch_joint.pos | -0.010823 | 0.024806 | 0.014534 | 0.750801 | ⚠️ SPIKE |
| 14 | right_wrist_yaw_joint.pos | -0.000001 | 0.016821 | 0.003552 | 0.820307 | ⚠️ SPIKE |
| 15 | right_gripper_joint.pos | 0.000542 | 0.016307 | 0.005422 | 0.288441 | ✅ OK |

---

## Conclusion

The dataset shows generally good quality with most joints having minimal gaps between state and action. The main concerns are:

1. **Systematic bias in shoulder roll joints** (joints 1 and 9) - requires investigation
2. **Occasional large spikes** in shoulder pitch and wrist joints - may need outlier filtering
3. **Overall data quality is good** with 99%+ of frames within normal ranges

The identified issues are unlikely to prevent successful policy training but addressing them could improve performance, especially for the shoulder roll joints which show the most significant systematic deviation.
