"""Configurable thresholds and requirement lists for the BHRT engine.

Every number here is a clinic policy decision; change it here (and in
docs/BHRT_TOOL.md) rather than inside the engine.
"""

from __future__ import annotations

# ---------------------------------------------------------------- freshness
LAB_MAX_AGE_DAYS = 90  # labs older than this count as missing
IMAGING_MAX_AGE_DAYS = 365  # mammogram / breast US / TVUS

# ---------------------------------------------------------------- required labs
# Decision-critical items block the draft when missing. All other items of the DKi BHRT
# panel (panel.py) are listed as 套餐缺项; set PACKAGE_ITEMS_BLOCK = True to make them blocking too.
FEMALE_REQUIRED_LABS = (
    "e2",
    "fsh",
    "total_t",
    "prl",
    "tsh",
    "alt",
    "ast",
    "creatinine",
    "tc",
    "tg",
    "ldl",
    "hb",
    "hct",
)
FEMALE_CYCLING_REQUIRED = ("progesterone",)
FEMALE_HSDD_REQUIRED = ("shbg",)  # needed before female testosterone
MALE_REQUIRED_LABS = (
    "total_t",
    "hct",
    "hb",
    "psa",
    "lh",
    "fsh",
    "e2",
    "prl",
    "alt",
    "ast",
    "creatinine",
    "tc",
    "tg",
    "ldl",
)
FATIGUE_EXTRA_LABS = ("b12",)  # outside the panel; suggested when fatigue / brain fog
PACKAGE_ITEMS_BLOCK = False

# ---------------------------------------------------------------- lab thresholds (canonical units)
ALT_ULN = 40.0  # U/L
AST_ULN = 40.0
LIVER_HOLD_MULTIPLE = 3.0  # >3x ULN -> HOLD
CREATININE_ULN = {"female": 84.0, "male": 106.0}  # umol/L
LDL_HIGH = 4.1  # mmol/L
LDL_VERY_HIGH = 4.9
TG_HIGH = 2.3
TG_VERY_HIGH = 5.6
GLUCOSE_IFG = 6.1
GLUCOSE_DM = 7.0
HBA1C_DM = 6.5
TSH_LOW = 0.27
TSH_HIGH = 4.2
HB_LOW_FEMALE = 110.0  # g/L
HCT_HIGH_FEMALE = 48.0  # %
HCT_CAUTION_MALE = 50.0
HCT_HOLD_MALE = 54.0
PSA_HOLD = 4.0  # ng/mL
FEMALE_TOTAL_T_ULN = 2.0  # nmol/L, upper premenopausal physiologic range (lab-specific; adjust)
FSH_POSTMENOPAUSAL = 25.0  # IU/L, supportive of late transition / postmenopause
MALE_T_LOW = 9.2  # nmol/L (264 ng/dL, Endocrine Society)
MALE_T_BORDERLINE = 12.0
PRL_ULN = {"female": 25.0, "male": 18.0}  # ng/mL
PRL_HOLD_MULTIPLE = 2.0
MALE_E2_HIGH = 50.0  # pg/mL
DHEAS_LOW = {"female": 35.0, "male": 80.0}  # ug/dL
CA125_ULN = 35.0  # U/mL
CA153_ULN = 25.0  # U/mL
CEA_ULN = 5.0  # ng/mL
AFP_ULN = 20.0  # ng/mL
CA199_ULN = 37.0  # U/mL
HCY_HIGH = 15.0  # umol/L
HSCRP_HIGH = 3.0  # mg/L
TPOAB_ULN = 34.0  # IU/mL
HOMA_IR_HIGH = 2.5
APOB_HIGH = 1.3  # g/L
OH2_16_LOW = 2.0
VITD_DEFICIENT = 20.0  # ng/mL
FERRITIN_LOW = 30.0  # ng/mL
B12_LOW = 200.0  # pg/mL

# ---------------------------------------------------------------- vitals
BP_UNCONTROLLED = (160, 100)  # HOLD
BP_ELEVATED = (140, 90)  # caution
BMI_OBESE = 30.0

# ---------------------------------------------------------------- imaging
# Postmenopausal endometrial thickness (mm) on TVUS
ENDOMETRIUM_POSTMENO_BLEEDING_MM = 4.0
ENDOMETRIUM_POSTMENO_ASYMPTOMATIC_MM = 11.0

# ---------------------------------------------------------------- pellets
E2_PELLET_PEAK_FLAG = 200.0  # pg/mL
E2_PELLET_REINSERT_MAX = 150.0

# ---------------------------------------------------------------- symptoms (MRS item index, 0-based)
MRS_ITEMS = (
    "潮热、出汗",
    "心脏不适（心悸、心跳加快）",
    "睡眠问题",
    "抑郁情绪",
    "易激惹",
    "焦虑",
    "体力和精神疲惫",
    "性方面问题",
    "泌尿问题",
    "阴道干涩",
    "关节和肌肉不适",
)
(
    MRS_HOT_FLASH,
    MRS_HEART,
    MRS_SLEEP,
    MRS_DEPRESS,
    MRS_IRRITABLE,
    MRS_ANXIETY,
    MRS_FATIGUE,
    MRS_SEX,
    MRS_BLADDER,
    MRS_DRYNESS,
    MRS_JOINT,
) = range(11)
MRS_SIGNIFICANT = 2  # item score >= this counts as a present complaint (0-4 scale)
MRS_SEVERITY = ((4, "无/轻微"), (8, "轻度"), (15, "中度"), (44, "重度"))

ADAM_ITEMS = (
    "性欲减退",
    "精力不足",
    "体力或耐力下降",
    "身高变矮",
    "生活乐趣减少",
    "情绪低落或易怒",
    "勃起不如以前坚挺",
    "运动能力下降",
    "饭后易犯困",
    "工作表现下降",
)
