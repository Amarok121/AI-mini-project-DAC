from app.schemas.agent_result import (
    PerformanceGapResult, 
    RegulatoryConflictResult,
    ScientificAgentOutput,
    IndustrialAgentOutput,
    RegulatoryAgentOutput
)

def analyze_regulatory_conflict(
    sci: ScientificAgentOutput,
    ind: IndustrialAgentOutput,
    reg: RegulatoryAgentOutput
) -> list[RegulatoryConflictResult]:
    """[Layer 3] 규제 및 인센티브 정합성 분석 (Spec 2.4/2.3 기반)"""
    conflicts = []

    # 1. 지원 격차 (Incentive Gap): 논문 신뢰도가 낮거나 실험실 수준인데 대규모 지원책만 언급된 경우
    is_experimental = (sci.overall_grade == 'LOW') or any(kw in sci.summary.lower() for kw in ['lab-scale', 'experimental', '초기'])
    has_large_scale_incentive = any(kw in str(reg.incentives).lower() for kw in ['실증', '대규모', 'utility', '상용화'])
    
    if is_experimental and has_large_scale_incentive:
        conflicts.append(RegulatoryConflictResult(
            conflict_type='INCENTIVE_GAP',
            severity='MED',
            description="보조금 수혜 타겟 불일치 가능성",
            analyst_note="과학적 근거는 실험실/초기 수준이나, 식별된 지원책은 상용화 실증 단계를 요구할 수 있음."
        ))

    # 2. 리스크 충돌: 규제 리스크가 존재하는데 산업적 신호(특허/뉴스)는 상용화를 낙관하는 경우
    if reg.risks and ind.overall_level == 'HIGH':
        conflicts.append(RegulatoryConflictResult(
            conflict_type='MARKET_REG_MISMATCH',
            severity='HIGH',
            description="시장 낙관론 대비 규제 리스크 존재",
            analyst_note=f"산업적 지표는 높으나, 실제 적용 시 {len(reg.risks)}건의 규제/법적 리스크가 걸림돌이 될 수 있음."
        ))

    return conflicts

def analyze_performance_gaps(
    sci: ScientificAgentOutput,
    ind: IndustrialAgentOutput
) -> list[PerformanceGapResult]:
    """[Spec 2.4] 뉴스 vs 논문 간 과장 여부 / 조건 누락 판정"""
    gaps = []
    
    # 예: 논문의 GRADE 수준과 뉴스의 CRAAP 수준 차이 탐지
    if sci.overall_grade == 'LOW' and ind.overall_level == 'HIGH':
        gaps.append(PerformanceGapResult(
            metric='Credibility Gap',
            sci_val=0.3,
            ind_val=0.8,
            hype_index=2.6,
            status='Hype Warning',
            description="과학적 근거 대비 산업적 기대치 과다",
            analyst_note="논문은 초기 단계(LOW GRADE)이나 뉴스는 상용화를 강하게 시사하고 있어 과장 가능성이 높음."
        ))

    return gaps
