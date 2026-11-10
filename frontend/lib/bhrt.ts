// Types mirroring backend/app/domain/bhrt (engine output + catalogue).

export interface BhrtAnalyte {
  code: string;
  name_zh: string;
  canonical_unit: string;
  units: string[];
  free_unit: boolean;
  qualitative: boolean;
  group: string;
}

export interface BhrtProduct {
  code: string;
  hormone_en: string;
  hormone_zh: string;
  name_zh: string;
  strength: string;
  equivalent: string;
  mg_per_ml: number | null;
  route: string;
  on_form: boolean;
}

export interface PanelItem {
  no: number;
  category: string;
  name: string;
  codes: string[];
  female: boolean;
  male: boolean;
  imaging_code: string | null;
}

export interface BhrtCatalog {
  engine_version: string;
  click_mg_cream: number;
  click_ml: number;
  container_ml: number;
  clicks_per_container: number;
  products: BhrtProduct[];
  form_instructions: { en: string; zh: string }[];
  panel: PanelItem[];
  analytes: BhrtAnalyte[];
  mrs_items: string[];
  adam_items: string[];
}

// Printed on the prescription only; never sent to the backend.
export interface PatientIdentity {
  name: string;
  patientId: string;
  address: string;
  tel: string;
  doctor: string;
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
  imaging: { birads: number | null; endometrial_thickness_mm: number | null; fibroids: boolean | null; done: string[] };
  unmatched_lines: number;
  warnings: string[];
}

export interface MissingItem { category: string; item: string; required: boolean; reason: string }
export interface LabOut { code: string; name_zh: string; value: number; unit: string; collected_on: string | null; flag: string; note: string; display: string }
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
