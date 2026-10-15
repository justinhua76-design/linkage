export interface Issue {
  code: string;
  field: string;
  message: string;
  severity: "error" | "warning";
}

export interface Patient {
  id: string;
  pseudonym: string;
  sex: string;
  birth_date: string | null;
  is_synthetic: boolean;
  created_at: string;
  created_by: string;
}

export interface BiomarkerMeta {
  code: string;
  name_en: string;
  name_zh: string;
  canonical_unit: string;
  allowed_units: string[];
  plausible_low: number;
  plausible_high: number;
  reference_low: number;
  reference_high: number;
  supports_lod: boolean;
  notes: string;
}

export interface ModelInfo {
  model_id: string;
  model_version: string;
  engine_version: string;
  coefficients_sha256: string;
  algorithm_source: string;
}

export interface Catalog {
  model: ModelInfo;
  biomarkers: BiomarkerMeta[];
  age_hard_range: [number, number];
  age_training_range: [number, number];
  lod_policy: string;
}

export interface Measurement {
  code: string;
  original_value: number | null;
  original_unit: string | null;
  normalised_unit: string | null;
  canonical_value: number | null;
  canonical_unit: string;
  conversion_factor: number | null;
  quality_status: string;
  reference_low: number;
  reference_high: number;
  below_lod: boolean;
  lod_canonical: number | null;
  imputation: string | null;
  collected_on: string | null;
}

export interface PhenoAgeResult {
  status: "ok";
  result_id: string | null;
  patient_id: string | null;
  phenoage: number;
  phenoage_rounded: number;
  chronological_age: number;
  phenoage_minus_chronological_age: number;
  mortality_score: number;
  linear_predictor: number;
  lod_policy: string;
  computed_at: string;
  model: ModelInfo;
  inputs: Measurement[];
  lab_result_ids: string[];
  warnings: Issue[];
  disclaimer: string;
}

export interface LabResult {
  id: string;
  patient_id: string;
  biomarker: string;
  value_original: number | null;
  unit_original: string;
  value_canonical: number | null;
  unit_canonical: string;
  conversion_factor: number | null;
  below_lod: boolean;
  lod_original: number | null;
  collected_on: string;
  source: string;
  source_detail: string | null;
  reference_low: number | null;
  reference_high: number | null;
  reference_unit: string | null;
  reference_source: string;
  quality_status: string;
  quality_issues: Issue[];
  created_at: string;
  created_by: string;
}

export interface ResultSummary {
  id: string;
  model_id: string;
  model_version: string;
  chronological_age: number;
  phenoage: number;
  mortality_score: number;
  computed_at: string;
  computed_by: string;
}

export interface Overview {
  patient: Patient;
  latest_labs: Record<string, LabResult>;
  labs: LabResult[];
  results: ResultSummary[];
}

export interface ApiError {
  status: string;
  code: string;
  message: string;
  errors?: Issue[];
  warnings?: Issue[];
}
