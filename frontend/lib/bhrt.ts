// Types mirroring backend/app/domain/bhrt (engine output + catalogue).

export interface BhrtAnalyte {
  code: string;
  name_zh: string;
  canonical_unit: string;
  units: string[];
  group: string;
}

export interface BhrtProduct {
  code: string;
  name_zh: string;
  route: string;
  strength: string;
  package: string;
  mg_per_unit: number | null;
  unit_label: string;
  confirmed: boolean;
  note: string;
}

export interface BhrtCatalog {
  engine_version: string;
  click_mg_cream: number;
  clicks_per_container: number;
  products: BhrtProduct[];
  analytes: BhrtAnalyte[];
  mrs_items: string[];
  adam_items: string[];
}

export interface ParsedLab {
  code: string;
  name_zh: string;
  value: number;
  unit: string | null;
  unit_recognised: boolean;
  below_detection: boolean;
  source_line: string;
}

export interface ParseResult {
  labs: ParsedLab[];
  imaging: { birads: number | null; endometrial_thickness_mm: number | null; fibroids: boolean | null };
  unmatched_lines: number;
  warnings: string[];
}

export interface MissingItem { category: string; item: string; required: boolean; reason: string }
export interface LabOut { code: string; name_zh: string; value: number; unit: string; collected_on: string | null; flag: string; note: string }
export interface Risk { level: "STOP" | "HOLD" | "CAUTION" | "INFO"; code: string; title: string; detail: string; action: string; scope: string }
export interface RxItem {
  product_code: string;
  product_name: string;
  strength: string;
  dose: string;
  active_dose: string;
  route_site: string;
  frequency: string;
  duration_quantity: string;
  purpose: string;
  pending_spec: boolean;
}
export interface FollowUp { when: string; label: string; items: string[] }

export interface Evaluation {
  status: "incomplete" | "stop" | "hold" | "draft";
  status_label: string;
  engine_version: string;
  client_ref: string;
  sex: "female" | "male";
  age: number;
  bmi: number | null;
  bp: string | null;
  stage: { code: string; label: string; implication: string };
  missing: MissingItem[];
  labs: LabOut[];
  lab_errors: string[];
  risks: Risk[];
  gate: string;
  symptoms: {
    scale: string;
    total?: number;
    severity?: string;
    somatic?: number;
    psychological?: number;
    urogenital?: number;
    top_complaints?: string[];
    positive?: boolean;
    yes_count?: number;
    items?: string[];
    map: { symptom: string; lever: string; check_first: string }[];
  };
  route: { selected: string | null; selected_label: string; reasons: string[]; pellet_blockers: string[] };
  prescription: RxItem[];
  endometrial_protection: string;
  client_instructions: string[];
  referrals: string[];
  monitoring: FollowUp[];
  expected_outcomes: { domain: string; onset: string; track: string }[];
  deviations: string[];
  assumptions: string[];
  pending: string[];
}
