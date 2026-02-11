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
    phone_verified?: boolean | null;
    auth_method?: string | null;
    onboarding_completed?: boolean | null;
    onboarding_source?: string | null;
    context_version?: number | null;
    last_context_build?: string | null;
    communication_paused?: boolean | null;
    quiet_hours_start?: string | null;
    quiet_hours_end?: string | null;
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
    referral_code?: string | null;
    qr_code_url?: string | null;
    created_at?: string | null;
};

export type ProviderList = {
    items: ProviderOut[];
    total: number;
};

export type ProviderReferral = {
    id: string;
    name: string;
    practice_name?: string | null;
    referral_code: string;
    qr_code_url?: string | null;
};

export type OnboardingResponse = {
    patient_id: string;
    provider_id: string;
    phone: string;
    debug_code?: string | null;
};

export type OtpRequestResponse = {
    status: string;
    debug_code?: string | null;
};

export type OtpVerifyResponse = {
    patient_id: string;
    provider_id?: string | null;
    expires_at: string;
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

export type LabResultList = {
    items: LabResultOut[];
    total: number;
};

export type VoiceCallOut = {
    id: string;
    patient_id: string;
    vapi_call_id?: string | null;
    direction: string;
    call_type: string;
    status: string;
    started_at?: string | null;
    ended_at?: string | null;
    duration_seconds?: number | null;
    transcript?: string | null;
    summary?: string | null;
    context_version_used?: number | null;
    escalated?: boolean | null;
    escalation_reason?: string | null;
    created_at?: string | null;
};

export type VoiceCallList = {
    items: VoiceCallOut[];
    total: number;
};

export type SmsMessageOut = {
    id: string;
    patient_id: string;
    telnyx_message_id?: string | null;
    direction: string;
    message_type?: string | null;
    content?: string | null;
    media_urls?: string[] | null;
    status?: string | null;
    ai_response?: string | null;
    sent_at?: string | null;
    delivered_at?: string | null;
    created_at?: string | null;
};

export type SmsMessageList = {
    items: SmsMessageOut[];
    total: number;
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
