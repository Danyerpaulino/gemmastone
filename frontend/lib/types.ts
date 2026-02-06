export type PatientOut = {
    id: string;
    provider_id?: string | null;
    mrn?: string | null;
    first_name: string;
    last_name: string;
    date_of_birth?: string | null;
    email?: string | null;
    phone?: string | null;
    contact_preferences?: Record<string, boolean> | null;
    created_at?: string | null;
};

export type PatientList = {
    items: PatientOut[];
    total: number;
};

export type ProviderOut = {
    id: string;
    email: string;
    name: string;
    npi?: string | null;
    specialty?: string | null;
    practice_name?: string | null;
    created_at?: string | null;
};

export type ProviderList = {
    items: ProviderOut[];
    total: number;
};

export type StoneAnalysisOut = {
    id: string;
    patient_id: string;
    provider_id: string;
    ct_scan_date?: string | null;
    stones_detected?: Array<Record<string, unknown>>;
    predicted_composition?: string | null;
    composition_confidence?: number | null;
    total_stone_burden_mm3?: number | null;
    hydronephrosis_level?: string | null;
    treatment_recommendation?: string | null;
    treatment_rationale?: string | null;
    urgency_level?: string | null;
    provider_approved?: boolean | null;
    provider_notes?: string | null;
    created_at?: string | null;
};

export type StoneAnalysisList = {
    items: StoneAnalysisOut[];
    total: number;
};

export type PreventionPlanOut = {
    id: string;
    analysis_id: string;
    patient_id: string;
    dietary_recommendations?: Array<Record<string, unknown>>;
    fluid_intake_target_ml?: number | null;
    medications_recommended?: Array<Record<string, unknown>>;
    lifestyle_modifications?: string[];
    education_materials?: Array<Record<string, unknown>>;
    personalized_summary?: string | null;
    active?: boolean | null;
    created_at?: string | null;
};

export type ComplianceLogOut = {
    id: string;
    patient_id: string;
    log_date: string;
    fluid_intake_ml?: number | null;
    medication_taken?: boolean | null;
    dietary_compliance_score?: number | null;
    notes?: string | null;
    created_at?: string | null;
};

export type ComplianceLogList = {
    items: ComplianceLogOut[];
    total: number;
};

export type LabResultOut = {
    id: string;
    patient_id: string;
    analysis_id?: string | null;
    result_type: string;
    result_date?: string | null;
    results: Record<string, unknown>;
    created_at?: string | null;
};

export type StoneMesh = {
    vertices: number[][];
    faces: number[][];
};

export type MeshResponse = {
    available: boolean;
    metadata?: Record<string, unknown> | null;
    meshes: StoneMesh[];
};
