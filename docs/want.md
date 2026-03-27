# **스마트 팩토리 제조 운영 대시보드 설계를 위한 도메인 중심의 계층적 가시성 체계 및 실무 구현 로드맵 분석**

## **제조 운영 가시성의 패러다임 변화와 대시보드의 전략적 가치**

현대적 제조 환경에서 스마트 팩토리의 성공은 단순히 설비를 자동화하는 것을 넘어, 현장에서 발생하는 방대한 데이터를 어떻게 의미 있는 인사이트로 전환하여 의사결정 속도를 높이는가에 달려 있다.1 이러한 맥락에서 제조 운영 대시보드는 공장 전반의 신경계와 같은 역할을 수행하며, 물리적 세계의 생산 공정을 디지털 환경에 투영하는 핵심적인 인터페이스로 자리 잡았다.3 과거의 생산 현황판이 사후적인 결과 보고에 그쳤다면, 최신 제조 운영 관리(MOM) 및 제조 실행 시스템(MES) 기반의 대시보드는 실시간 가시성(Real-time Visibility)을 바탕으로 예측적이고 자율적인 운영을 지원하는 방향으로 진화하고 있다.5

지멘스(Siemens)와 SAP, 로크웰 오토메이션(Rockwell Automation) 등 글로벌 리더들이 제시하는 기술적 지향점은 정보 기술(IT)과 운영 기술(OT)의 완벽한 융합을 통한 단일 진실 공급원(Single Source of Truth)의 구축이다.8 이는 공장 바닥(Shop Floor)의 센서 데이터와 기업 상단(Top Floor)의 자원 관리 데이터를 결합하여, 단순한 수치 나열이 아닌 비즈니스 맥락이 포함된 실행 가능한 정보를 제공하는 것을 의미한다.10 대시보드 설계의 본질은 이러한 복잡한 데이터 구조를 사용자의 인지 능력에 맞게 단순화하고, 각 역할자가 직면한 특정 문제를 해결하는 데 필요한 정보를 계층적으로 배치하는 데 있다.13

대시보드의 전략적 가치는 생산성 지표인 종합 설비 효율(OEE)의 극대화뿐만 아니라 품질 규정 준수, 에너지 지속 가능성, 그리고 안전 관리 등 다차원적인 영역으로 확장되고 있다.16 특히 최근의 대시보드는 고성능 HMI(High Performance HMI) 설계 원칙을 준수함으로써 작업자의 상황 인식(Situational Awareness)을 높이고, 비정상 상황 발생 시 대응 시간을 획기적으로 단축하여 제조 경쟁력을 강화하는 필수적인 도구가 되었다.13

## **고성능 HMI 설계 철학과 ISA-101 표준의 실무 적용**

제조 운영 대시보드 설계의 가장 근본적인 지침이 되는 ISA-101 표준은 단순한 심미적 디자인이 아닌, 작업자의 인지 부하를 최소화하고 상황 판단 능력을 극대화하는 '고성능 HMI'를 지향한다.13 전통적인 HMI가 설비의 외형을 그대로 모사하는 3D 그래픽과 화려한 색상을 사용하여 정보의 중요도를 희석했던 것과 달리, 고성능 HMI는 철저하게 정보 중심의 절제된 표현 방식을 채택한다.21

### **상황 인식 능력을 높이는 시각적 언어**

고성능 HMI 설계의 핵심은 '정상 상태는 지루하게, 이상 상태는 명확하게' 표현하는 것이다.13 이를 위해 배경색으로 연한 회색이나 중성 톤을 사용하여 눈의 피로를 줄이고 화면의 눈부심을 방지한다.25 설비의 외형은 입체적인 3D 형태가 아닌 평면적인 2D 아이콘으로 간소화하며, 불필요한 장식적 요소나 애니메이션(회전하는 펌프, 흐르는 액체 등)은 작업자의 주의를 분산시키므로 배제한다.21

색상은 오직 경람(Alarm)이나 비정상적인 편차를 알리는 신호로만 매우 제한적으로 사용된다.13 이러한 설계 하에서 무채색 위주의 화면에 붉은색이나 노란색이 나타나면 작업자는 즉각적으로 해당 지점에 문제가 발생했음을 인지할 수 있다.13 연구에 따르면 이러한 설계 방식은 비정상 상황 감지 능력을 기존 대비 5배 이상 높이고, 문제 해결 시간을 40% 이상 단축시키는 것으로 나타났다.19

### **데이터의 맥락화와 아날로그 표시기**

단순한 숫자의 나열은 데이터일 뿐 정보가 될 수 없다. 예를 들어 특정 설비의 온도가 85도라는 숫자는 그 자체가 높은 것인지 낮은 것인지 즉각적으로 알기 어렵다.29 고성능 HMI에서는 숫자를 단독으로 표시하기보다 무빙 아날로그 표시기(Moving Analog Indicator)를 사용하여 현재 값이 정상 운전 범위(Setpoint) 내에 있는지, 상한 또는 하한 경계선에 얼마나 근접했는지를 시각적으로 보여준다.25 또한 스파크라인(Sparkline)과 같은 미세 트렌드 그래프를 현재 값 옆에 배치하여 데이터가 상승 중인지 하강 중인지의 변화 추세를 한눈에 파악할 수 있도록 돕는다.27

| 설계 원칙 | 전통적 HMI 특성 | 고성능 HMI(ISA-101) 특성 | 기대 효과 |
| :---- | :---- | :---- | :---- |
| **배경색** | 검정색 또는 원색 | 연한 회색(RGB 192, 192, 192 등) | 눈의 피로 감소 및 눈부심 방지 25 |
| **그래픽 형태** | 화려한 3D, 실물 모사 | 단순한 2D 평면 아이콘 | 정보 전달의 명확성 증대 21 |
| **색상 활용** | 장식적 목적으로 다수 사용 | 경람 및 이상 상태에만 제한 사용 | 이상 징후의 즉각적 식별 13 |
| **데이터 표현** | 단순 숫자(Value) 위주 | 맥락이 포함된 아날로그 지표 및 트렌드 | 빠른 상황 판단 및 대응 25 |
| **인터랙션** | 다수의 애니메이션 포함 | 애니메이션 배제 (이상 상태 제외) | 인지 부하 감소 13 |

## **제조 운영 대시보드의 4단계 계층 구조 분석**

정보의 효과적인 전달을 위해 ISA-101은 대시보드를 네 가지 수준(Level)으로 구분하는 계층적 구조를 권장한다.30 이 구조는 사용자가 전체적인 상황을 먼저 파악하고, 필요에 따라 세부 정보로 단계적으로 접근하는 점진적 노출(Progressive Disclosure) 원칙을 따른다.23

### **수준 1: 프로세스 영역 개요 (Process Area Overview)**

수준 1 화면은 공장 전체 또는 특정 생산 라인 전체의 통합 관제 화면이다.29 대형 비디오 월이나 상황실의 중앙 모니터에 상시 표시되는 화면으로, 개별 설비의 상태보다는 전체 공정의 흐름과 주요 KPI를 중심으로 구성된다.11 OEE(종합 설비 효율), 당일 목표 대비 실적 달성률, 주요 품질 지수, 현재 활성화된 중요 경람의 수 등이 포함되며, 이를 통해 관리자는 공장이 계획대로 운영되고 있는지를 단 몇 초 만에 판단할 수 있다.19

### **수준 2: 공정 단위 제어 (Process Unit Control)**

수준 2 화면은 작업자가 일상적인 업무의 90% 이상을 수행하는 가장 핵심적인 주 화면이다.34 특정 공정 섹션이나 설비 그룹의 상세한 운전 상태를 보여주며, 주요 제어 루프, 밸브 및 모터의 상태, 공정 변수의 상세 추세가 포함된다.29 작업자는 이 화면에서 직접적인 조작을 수행하며, 비정상 상황이 감지될 경우 즉시 조치를 취하거나 수준 3 화면으로 이동하여 원인을 파악한다.30

### **수준 3: 공정 단위 상세 (Process Unit Detail)**

수준 3은 특정 개별 설비나 루프의 상세 진단을 위한 화면이다.30 예를 들어 펌프 하나에 대한 가동 시간, 고장 이력, 진동 수치, 연동된 인터락(Interlock) 상태 등을 상세히 표시한다.30 평상시에는 거의 보지 않지만, 경람이 발생하여 정밀한 분석이 필요할 때 사용된다.30 팝업(Pop-up) 창 형태를 활용하여 수준 2 화면의 맥락을 유지하면서 세부 정보를 제공하는 방식이 선호된다.34

### **수준 4: 프로세스 단위 지원 및 진단 (Process Unit Support)**

수준 4는 일상 운영보다는 유지보수나 기술 분석을 위한 화면이다.30 PLC의 I/O 상태, 통신 진단 데이터, 상세한 유지보수 매뉴얼, 설계 도면(P\&ID) 등이 포함된다.23 그래픽보다는 텍스트와 로그 데이터 중심의 정보 밀도가 매우 높은 화면으로 구성되며, 시스템 관리자나 정비 전문가가 주로 사용한다.19

## **플랫폼별 대시보드 구현 특성 및 레퍼런스 사례 연구**

글로벌 제조 솔루션 플랫폼들은 각기 다른 철학과 기술적 강점을 바탕으로 대시보드 도구를 제공하고 있다. 이들 플랫폼의 공식 데모와 매뉴얼을 분석하면 실무에 즉시 적용 가능한 설계 패턴을 도출할 수 있다.

### **지멘스 Opcenter: 데이터 모델링 기반의 지능형 대시보드**

지멘스의 Opcenter MES는 의미론적 데이터 모델(Semantic Data Model)을 바탕으로 한 강력한 분석 기능을 제공한다.37 Opcenter BI Quickstart는 MES 내의 복잡한 원시 데이터를 가공하여 OEE, 수율, 사이클 타임과 같은 표준 KPI로 자동 변환하는 프리빌트(Pre-built) 모델을 갖추고 있다.37

지멘스 대시보드의 특징은 유연한 프레젠테이션 레이어 통합에 있다.37 사용자는 지멘스에서 제공하는 기본 대시보드 외에도 Power BI나 Tableau와 같은 범용 BI 도구를 Opcenter의 데이터 모델 위에 얹어 고도화된 시각화를 구현할 수 있다.37 특히 SMT(표면 실장 기술) 라인이나 고정밀 테스트 공정 등 하이테크 제조 환경에 특화된 실시간 모니터링 레이아웃을 제공하여 임원진에게는 전사적 관점을, 현장 작업자에게는 실행 중심의 관점을 제공한다.37

### **SAP Digital Manufacturing: 작업자 중심의 POD 프레임워크**

SAP Digital Manufacturing(SAP DM)의 대시보드 전략은 생산 운영자 대시보드(POD)라는 강력한 프레임워크에 집약되어 있다.39 SAP DM의 POD는 단순한 모니터링 화면을 넘어 작업자가 시스템과 상호작용하는 핵심 워크스테이션이다.41

SAP POD의 가장 큰 특징은 플러그인(Plug-in) 기반의 모듈형 구조다.42 POD 디자이너라는 로우코드 도구를 통해 드래그 앤 드롭 방식으로 작업 지시서 뷰어, 데이터 수집 폼, 불량 보고 버튼 등을 배치하여 공정 특성에 맞는 인터페이스를 신속하게 구축할 수 있다.39 또한 내장된 SAP Analytics Cloud(eSAC)를 활용해 별도의 데이터 복제 없이 실시간 분석 인사이트를 화면에 직접 포함할 수 있으며, 이는 주문 실행 추적이나 공정 흐름 시각화에 탁월한 성능을 발휘한다.44

### **AVEVA Unified Operations Center: 시스템의 시스템 통합**

AVEVA의 Unified Operations Center(UOC)는 '단일 창 가시성(Single Pane of Glass)'을 목표로 하며, 공장의 모든 서브시스템(MES, SCADA, ERP, CCTV, GIS 등)을 하나로 묶는 '시스템의 시스템' 아키텍처를 지향한다.7

AVEVA UOC는 지리 정보 시스템(GIS)과 통합된 지도 기반 내비게이션 모델을 사용하여, 전 세계에 흩어진 공장들을 지도상에서 모니터링하다가 특정 공장, 특정 라인, 특정 펌프까지 원클릭으로 드릴다운하는 직관적인 탐색 환경을 제공한다.4 특히 엔지니어링 설계 단계의 3D 데이터와 실시간 운영 데이터를 결합한 디지털 트윈 시각화는 AVEVA만이 가진 강력한 차별점이다.7

### **로크웰 오토메이션 Plex: 클라우드 기반의 종이 없는 공장**

로크웰 오토메이션의 Plex MES는 100% 클라우드 네이티브 플랫폼으로서 실시간 제어와 종이 없는 운영을 강조한다.2 Plex의 작업자 제어 패널(Operator Control Panel)은 터치 최적화 인터페이스를 통해 작업자가 현장에서 즉시 설비 셋업 확인, 품질 체크, 가동 시간 로깅을 수행하도록 설계되었다.8

Plex 대시보드의 강점은 내장된 SPC(통계적 공정 제어) 차트 기능이다.12 측정값이 입력되는 즉시 관리도 상에 플로팅되어 공정의 통계적 이상 여부를 실시간으로 판정하며, 비정상 징후 발견 시 즉시 생산을 중단하거나 수정을 권고하는 조치 중심의 기능을 제공한다.6

## **도메인 및 역할별 이중 매핑을 통한 정보 우선순위 정의**

대시보드 설계의 실패 원인 중 상당수는 모든 사용자에게 동일한 정보를 제공하기 때문이다. 효과적인 대시보드를 위해서는 도메인(공정 성격)과 사용자 역할(Role)에 따른 정보 요구사항의 정밀한 매핑이 필요하다.15

### **역할별 정보 요구사항 및 우선순위 분석**

제조 현장의 핵심 역할자인 작업자, 관리자, 품질 관리자(QA)의 정보 요구사항은 다음과 같이 정의된다.53

| 사용자 역할 | 주요 목표 | 핵심 정보 요구사항 (우선순위) | 선호 인터페이스 형태 |
| :---- | :---- | :---- | :---- |
| **현장 작업자** | 당일 할당량 완수 및 무결점 생산 | 활성 작업 리스트, 디지털 작업 지시서, 실시간 불량 판정 결과, 설비 상태 알림 | 단순 리스트, 큰 버튼, 이미지 기반 가이드, 터치 스크린 |
| **관리자/슈퍼바이저** | 생산 흐름 최적화 및 자원 효율성 극대화 | OEE 요약, 공정 간 재공(WIP) 현황, 다운타임 원인 분석(파레토), 인력 할당 상태 | 게이지 차트, 추세 그래프, 샌키 다이어그램, 모바일 대시보드 |
| **품질 관리자(QA)** | 공정 안정성 확보 및 규제 준수 증명 | Cp/Cpk 지수, SPC 관리도, 결함 유형 분포, 이력 추적(Genealogy) 데이터 | 통계 차트, 히스토그램, 트리 구조 이력 뷰, 분석 보고서 |

### **도메인별 특화 정보 구성**

산업군별로 대시보드에 포함되어야 할 필수 도메인 정보 또한 상이하다.9

* **이산 제조(Discrete Manufacturing):** 조립 단계별 부품 정합성, 작업자 스킬 매트릭스, 공구 수명 관리 등이 중요하다.9  
* **프로세스 제조(Process Manufacturing):** 온도/압력/유량 등 미세 공정 변수, 레시피 준수율, 배치(Batch) 품질 관리, 원자재 농도 분석 등이 핵심이다.41  
* **규제 중심 산업(Pharma/Medical):** 전자 서명(E-signature) 상태, 감사 추적(Audit Trail), eDHR(전자 기기 이력 기록) 생성 상태 등이 최우선 순위로 배치되어야 한다.58

## **정보 밀도 관리와 고급 시각화 위젯 분석**

대시보드의 정보 밀도는 사용자의 가독성과 비례해야 한다. 고성능 대시보드 구현을 위한 주요 시각화 위젯과 그 활용 방안은 다음과 같다.

### **OEE 시각화와 6대 손실 분석 패턴**

OEE는 가동률(Availability), 성능(Performance), 품질(Quality)의 세 가지 요소가 곱해진 지표이므로, 종합 지수뿐만 아니라 각 구성 요소의 현재 상태를 함께 보여주어야 한다.35 특히 OEE를 깎아먹는 '6대 손실'을 시각화할 때는 단순 바 차트보다 파레토 차트를 사용하여 손실의 80%를 차지하는 20%의 핵심 원인을 식별하도록 유도해야 한다.35

### **흐름 및 병목 구간 분석을 위한 샌키 다이어그램**

공정 간의 물류 흐름이나 에너지 소모 경로를 시각화하는 데는 샌키 다이어그램이 가장 효과적이다.63 선의 두께가 흐름의 양을 나타내므로, 어느 구간에서 재공이 쌓이는지 또는 에너지가 낭비되는지(Loss)를 직관적으로 파악할 수 있다.65 AVEVA의 UOC 컨텐트 라이브러리 등에서 이러한 위젯을 기본적으로 제공하여 복잡한 물류 네트워크의 가시성을 확보한다.67

### **품질 및 통계적 공정 제어를 위한 SPC 위젯**

QA 담당자를 위한 품질 대시보드에서는 관리도(Control Chart)가 핵심이다. 단순한 런 차트와 달리 상하한 관리 한계선(UCL, LCL)을 표시하고, 규칙 위반(예: 7점 연속 상승 등) 발생 시 즉시 배경색을 변경하거나 알림을 띄우는 기능이 포함되어야 한다.51 인피니티QS(InfinityQS)의 Enact 플랫폼은 다단계 파레토 차트와 상자 수염 그림(Box-and-Whisker)을 결합하여 결함의 빈도와 변동성을 동시에 분석할 수 있는 고급 품질 위젯을 제공한다.54

## **단계별 대시보드 구현 로드맵: 최소 요건에서 상급 지능화까지**

성공적인 대시보드 구축은 한 번에 모든 기능을 구현하는 것이 아니라, 현장의 데이터 수집 역량과 조직의 디지털 성숙도에 맞춰 단계적으로 진행되어야 한다.72

### **1단계: 가시성 확보 단계 (Minimum Viable Dashboard)**

이 단계의 목표는 현장의 '블랙박스'를 제거하고 수작업 보고서를 자동화하는 것이다.

* **핵심 기능:** 실시간 설비 가동/정지 상태 모니터링, 목표 생산량 대비 실제 실적 표시(Andon), 기본 OEE 자동 산출, 주요 경람 알림.  
* **기술적 요건:** 주요 설비의 PLC 데이터 연동(OPC UA/MQTT), 관계형 데이터베이스 구축, 표준 웹 기반 대시보드 위젯 활용.17  
* **사용자 경험:** 현장 작업자가 멀리서도 볼 수 있는 대형 현황판 위주의 단순한 시각화.11

### **2단계: 최적화 및 협업 단계 (Recommended Standard)**

데이터가 축적되고 시스템 간 연동이 이루어지면, 분석 기능을 강화하고 역할별 맞춤형 정보를 제공한다.

* **핵심 기능:** 역할 기반 대시보드(작업자 POD, 관리자 분석 뷰), 다운타임 사유 상세 분석(6대 손실 파레토), 실시간 SPC 관리도, 원자재-제품 이력 추적(Genealogy).39  
* **기술적 요건:** ERP-MES-LIMS 데이터 통합, 로우코드 대시보드 디자이너 도입, 모바일/태블릿 반응형 레이아웃 적용.12  
* **사용자 경험:** 작업자에게는 3D 조립 지침과 디지털 체크리스트를 제공하고, 관리자에게는 원클릭 드릴다운 분석 기능을 제공하여 협업 효율을 극대화.41

### **3단계: 지능화 및 자율 운영 단계 (Advanced Intelligence)**

AI와 디지털 트윈 기술을 결합하여 미래를 예측하고 시스템이 스스로 최적의 대안을 제안하는 단계이다.

* **핵심 기능:** AI 비전 기반 자동 품질 검사 및 이상 탐지, 설비 고장 예지 보전(PdM) 및 잔여 수명(RUL) 예측, 디지털 트윈 기반 3D 통합 관제, 실시간 에너지 최적화 시나리오 분석.46  
* **기술적 요건:** 딥러닝 기반 이미지 분석 엔진, 엣지 컴퓨팅 기반의 실시간 추론 하드웨어, 3D 에셋 렌더링 엔진, 머신러닝 기반 예측 모델.37  
* **사용자 경험:** 생성형 AI 챗봇을 통한 운영 데이터 질의응답, 확장 현실(XR) 기반 원격 유지보수 지원, 상황 인지형 지능적 경람 필터링.48

## **결론 및 실무적 제언**

본 연구를 통해 분석된 글로벌 제조 소프트웨어 리더들의 대시보드 설계 패턴은 단순히 보기 좋은 화면을 만드는 것이 아니라, 제조 현장의 복잡성을 관리 가능한 수준으로 단순화하고 의사결정의 질을 높이는 데 초점이 맞춰져 있다.37

성공적인 대시보드 설계를 위한 실무적 핵심 제언은 다음과 같다. 첫째, ISA-101 표준을 전사적인 대시보드 디자인 가이드로 채택하여 시각적 일관성을 확보하고 인지 효율을 높여야 한다.13 둘째, 데이터 설계 단계에서부터 의미론적 연결(Semantic Link)을 고려하여 사용자가 별도의 분석 없이도 인과관계를 파악할 수 있는 맥락을 제공해야 한다.37 셋째, 현장 작업자의 실제 작업 동선과 모바일 기기 사용 환경을 고려하여 조작 단계를 최소화한 '조치 가능 중심(Action-Oriented)' 대시보드를 구축해야 한다.14

이러한 단계적 접근과 표준 기반의 설계가 결합될 때, 대시보드는 단순한 모니터링 도구를 넘어 제조 기업의 지능적 성장을 견인하는 핵심 자산으로 기능하게 될 것이다.1

#### **참고 자료**

1. Plex's No BS Guide to MES | Rockwell Automation, 3월 14, 2026에 액세스, [https://plex.rockwellautomation.com/en-us/blog/plexs-no-bs-guide-mes.html](https://plex.rockwellautomation.com/en-us/blog/plexs-no-bs-guide-mes.html)  
2. Plex Manufacturing Execution System (MES) From Rockwell Automation \- ECM Connection, 3월 14, 2026에 액세스, [https://www.ecmconnection.com/doc/plex-manufacturing-execution-system-mes-from-rockwell-automation-0001](https://www.ecmconnection.com/doc/plex-manufacturing-execution-system-mes-from-rockwell-automation-0001)  
3. AVEVA Operations Control, 3월 14, 2026에 액세스, [https://www.aveva.com/content/dam/aveva/documents/datasheets/Datasheet\_OperationsControl.pdf.coredownload.inline.pdf](https://www.aveva.com/content/dam/aveva/documents/datasheets/Datasheet_OperationsControl.pdf.coredownload.inline.pdf)  
4. AVEVA™ Unified Operations Center for Data Centers, 3월 14, 2026에 액세스, [https://www.aveva.com/content/dam/aveva/documents/onesheet/OneSheet\_UOCDataCenters.pdf](https://www.aveva.com/content/dam/aveva/documents/onesheet/OneSheet_UOCDataCenters.pdf)  
5. Opcenter Manufacturing Operations Management \- Siemens, 3월 14, 2026에 액세스, [https://www.siemens.com/en-us/products/opcenter/](https://www.siemens.com/en-us/products/opcenter/)  
6. Maximizing Manufacturing Efficiency | Plex MES by Rockwell Automation, 3월 14, 2026에 액세스, [https://blog.cybertrol.com/maximizing-manufacturing-efficiency-plex-mes-by-rockwell-automation](https://blog.cybertrol.com/maximizing-manufacturing-efficiency-plex-mes-by-rockwell-automation)  
7. AVEVA™ Unified Operations Center, 3월 14, 2026에 액세스, [https://wcs-avevawcs-4sightassetautomation.swcontentsyndication.com/sw/swchannel/CustomerCenter/documents/101888/186785/Brochure\_AVEVA\_UnifiedOperationsCenter\_11-20.pdf](https://wcs-avevawcs-4sightassetautomation.swcontentsyndication.com/sw/swchannel/CustomerCenter/documents/101888/186785/Brochure_AVEVA_UnifiedOperationsCenter_11-20.pdf)  
8. Manufacturing Execution System (MES) / MOM | Rockwell Automation | Plex, 3월 14, 2026에 액세스, [https://www.rockwellautomation.com/content/plex/global/apac/en/products/manufacturing-execution-system.html](https://www.rockwellautomation.com/content/plex/global/apac/en/products/manufacturing-execution-system.html)  
9. Opcenter Execution \- Siemens, 3월 14, 2026에 액세스, [https://www.siemens.com/en-us/products/opcenter/execution/](https://www.siemens.com/en-us/products/opcenter/execution/)  
10. SAP Digital Manufacturing | Manufacturing Execution and Operations, 3월 14, 2026에 액세스, [https://www.sap.com/products/scm/digital-manufacturing.html](https://www.sap.com/products/scm/digital-manufacturing.html)  
11. AVEVA™ Unified Operations Center, 3월 14, 2026에 액세스, [https://www.aveva.com/en/products/unified-operations-center/](https://www.aveva.com/en/products/unified-operations-center/)  
12. Plex Manufacturing Execution System (MES) | FactoryTalk | IN \- Rockwell Automation, 3월 14, 2026에 액세스, [https://www.rockwellautomation.com/en-in/products/software/factorytalk/operationsuite/mes/plex-mes.html2.html](https://www.rockwellautomation.com/en-in/products/software/factorytalk/operationsuite/mes/plex-mes.html2.html)  
13. ISA-101 – The Standard for Modern, High-Performance HMI Interfaces \- IoT Industries, 3월 14, 2026에 액세스, [https://www.iotindustries.sk/en/blog/isa-101/](https://www.iotindustries.sk/en/blog/isa-101/)  
14. Best Practices for HMI Design in Industrial and Safety-Critical A \- Mouser Electronics, 3월 14, 2026에 액세스, [https://www.mouser.com/blog/best-practices-hmi-design-industrial-safety-critical-applications](https://www.mouser.com/blog/best-practices-hmi-design-industrial-safety-critical-applications)  
15. Dashboard Design: 7 Best Practices & Examples \- Qlik, 3월 14, 2026에 액세스, [https://www.qlik.com/us/dashboard-examples/dashboard-design](https://www.qlik.com/us/dashboard-examples/dashboard-design)  
16. OEE Dashboards \- Hexagon, 3월 14, 2026에 액세스, [https://hexagon.com/products/oee-dashboards](https://hexagon.com/products/oee-dashboards)  
17. Plex Smart Manufacturing Platform Plex Sustainable Solutions | Rockwell Automation, 3월 14, 2026에 액세스, [https://plex.rockwellautomation.com/en-us/videos/plex-smart-manufacturing-platform-plex-sustainable-solutions.html](https://plex.rockwellautomation.com/en-us/videos/plex-smart-manufacturing-platform-plex-sustainable-solutions.html)  
18. OEE Analytics for Manufacturing Productivity \- Siemens, 3월 14, 2026에 액세스, [https://www.siemens.com/en-us/products/industrial-digitalization-services/oee-analytics/](https://www.siemens.com/en-us/products/industrial-digitalization-services/oee-analytics/)  
19. A Guide to Modern HMI Creation \- Control \+ S \- WordPress.com, 3월 14, 2026에 액세스, [https://ricolsen1supervc.wordpress.com/2017/03/10/a-guide-to-modern-hmi-creation/](https://ricolsen1supervc.wordpress.com/2017/03/10/a-guide-to-modern-hmi-creation/)  
20. ISA101, Human-Machine Interfaces- ISA, 3월 14, 2026에 액세스, [https://www.isa.org/standards-and-publications/isa-standards/isa-standards-committees/isa101](https://www.isa.org/standards-and-publications/isa-standards/isa-standards-committees/isa101)  
21. High Performance Graphics to Maximize Operator Effectiveness \- ISA, 3월 14, 2026에 액세스, [https://www.isa.org/getmedia/06130a38-f7af-4b35-8c9c-2c34f25c1977/The-High-Performance-HMI-Overview-v2-01.pdf](https://www.isa.org/getmedia/06130a38-f7af-4b35-8c9c-2c34f25c1977/The-High-Performance-HMI-Overview-v2-01.pdf)  
22. What is High Performance HMI? 6 Key Principles of HPHMI \- MAC Automation, 3월 14, 2026에 액세스, [https://macautoinc.com/insights/high-performance-hmi/](https://macautoinc.com/insights/high-performance-hmi/)  
23. The High Performance HMI Handbook and You \- Part 1 | Corso Systems, 3월 14, 2026에 액세스, [https://corsosystems.com/posts/the-high-performance-hmi-handbook-and-you-part-1](https://corsosystems.com/posts/the-high-performance-hmi-handbook-and-you-part-1)  
24. HMI Design Best Practices: Creating Interfaces That Actually Help Operators \- Medium, 3월 14, 2026에 액세스, [https://medium.com/@sihambouguern/hmi-design-best-practices-creating-interfaces-that-actually-help-operators-436cbd79c3d4](https://medium.com/@sihambouguern/hmi-design-best-practices-creating-interfaces-that-actually-help-operators-436cbd79c3d4)  
25. Up Your Productivity and Safety with High Performance HMI Design—White Paper, 3월 14, 2026에 액세스, [https://www.emersonautomationexperts.com/2023/industrial-internet-things/up-your-productivity-and-safety-with-high-performance-hmi-design-white-paper/](https://www.emersonautomationexperts.com/2023/industrial-internet-things/up-your-productivity-and-safety-with-high-performance-hmi-design-white-paper/)  
26. High-Performance HMI Colors | Palettes and Inspiration \- RealPars, 3월 14, 2026에 액세스, [https://www.realpars.com/blog/hmi-colors](https://www.realpars.com/blog/hmi-colors)  
27. Situation Awareness: \- Adroit ISA 101 High Performance HMI, 3월 14, 2026에 액세스, [https://adroit-europe.com/Files/HighPerformanceHMI.pdf](https://adroit-europe.com/Files/HighPerformanceHMI.pdf)  
28. Using ISA-101 & High Performance HMIs for More Effective Operations \- Graham Nasby, 3월 14, 2026에 액세스, [https://www.grahamnasby.com/files\_publications/NasbyG\_2017\_HighPerformanceHMIs\_IntelligentWastewaterSeminar\_WEAO\_sept14-2017\_slides-public.pdf](https://www.grahamnasby.com/files_publications/NasbyG_2017_HighPerformanceHMIs_IntelligentWastewaterSeminar_WEAO_sept14-2017_slides-public.pdf)  
29. What Is High-Performance HMI? \- RealPars, 3월 14, 2026에 액세스, [https://www.realpars.com/blog/high-performance-hmi](https://www.realpars.com/blog/high-performance-hmi)  
30. Detailed Design Principles of High-Performance HMI Display \- RealPars, 3월 14, 2026에 액세스, [https://www.realpars.com/blog/hmi-display](https://www.realpars.com/blog/hmi-display)  
31. What is the deal with High-Performance-HMI? \- User Centered Design Services, 3월 14, 2026에 액세스, [https://mycontrolroom.com/what-is-the-deal-with-high-performance-hmi/](https://mycontrolroom.com/what-is-the-deal-with-high-performance-hmi/)  
32. Proficy Operations Hub 2022.04 from GE Digital \- VIX Automation, 3월 14, 2026에 액세스, [https://www.vix.com.pl/wp-content/uploads/2022/06/Operations-Hub-2022.04-datasheet.pdf](https://www.vix.com.pl/wp-content/uploads/2022/06/Operations-Hub-2022.04-datasheet.pdf)  
33. Situation Awareness \- ISA 101 High Performance HMI \- Adroit Technologies, 3월 14, 2026에 액세스, [https://adroit-europe.com/hphmi](https://adroit-europe.com/hphmi)  
34. High-Performance Graphics: Navigate the Hierarchical Layers with Storyboarding, 3월 14, 2026에 액세스, [https://insideautomation.net/navigate-the-hierarchical-layers-with-storyboarding/](https://insideautomation.net/navigate-the-hierarchical-layers-with-storyboarding/)  
35. OEE Dashboards: The northstar to your factory's productivity \- Factbird, 3월 14, 2026에 액세스, [https://www.factbird.com/blog/oee-dashboard](https://www.factbird.com/blog/oee-dashboard)  
36. Data Center Demo Project Download \- Ignition \- Inductive Automation Forum, 3월 14, 2026에 액세스, [https://forum.inductiveautomation.com/t/data-center-demo-project-download/85227](https://forum.inductiveautomation.com/t/data-center-demo-project-download/85227)  
37. Opcenter BI Quickstart \- Siemens, 3월 14, 2026에 액세스, [https://www.siemens.com/en-us/products/dhruv-technology-solutions-opcenter-bi-quickstart/](https://www.siemens.com/en-us/products/dhruv-technology-solutions-opcenter-bi-quickstart/)  
38. Opcenter Execution Electronics | Siemens, 3월 14, 2026에 액세스, [https://www.siemens.com/en-us/products/opcenter/execution/electronics/](https://www.siemens.com/en-us/products/opcenter/execution/electronics/)  
39. SAP Digital Manufacturing 2602 \- SAP Help Portal, 3월 14, 2026에 액세스, [https://help.sap.com/doc/13c9f83611f94a5ab2c94f23cacfc217/latest/en-US/SAP\_DMC\_FSD\_enUS.pdf](https://help.sap.com/doc/13c9f83611f94a5ab2c94f23cacfc217/latest/en-US/SAP_DMC_FSD_enUS.pdf)  
40. What Is SAP Digital Manufacturing? \- The SAP PRESS Blog, 3월 14, 2026에 액세스, [https://blog.sap-press.com/what-is-sap-digital-manufacturing](https://blog.sap-press.com/what-is-sap-digital-manufacturing)  
41. Understanding the Positioning of SAP Digital Manufacturing, 3월 14, 2026에 액세스, [https://learning.sap.com/courses/discovering-sap-digital-manufacturing/understanding-the-positioning-of-sap-digital-manufacturing\_b61aaaeb-66ee-45d0-86ef-03fd6e230058](https://learning.sap.com/courses/discovering-sap-digital-manufacturing/understanding-the-positioning-of-sap-digital-manufacturing_b61aaaeb-66ee-45d0-86ef-03fd6e230058)  
42. Exploring the POD Framework \- SAP Learning, 3월 14, 2026에 액세스, [https://learning.sap.com/courses/exploring-customization-in-sap-digital-manufacturing/exploring-the-pod-framework](https://learning.sap.com/courses/exploring-customization-in-sap-digital-manufacturing/exploring-the-pod-framework)  
43. Introducing the POD Designer UI \- SAP Learning, 3월 14, 2026에 액세스, [https://learning.sap.com/courses/exploring-customization-in-sap-digital-manufacturing/introduction-to-pod-designer-ui](https://learning.sap.com/courses/exploring-customization-in-sap-digital-manufacturing/introduction-to-pod-designer-ui)  
44. How to Create a Dashboard in SAP Digital Manufacturing in 5 Steps? \- concircle, 3월 14, 2026에 액세스, [https://blog.concircle.com/en/how-to-create-a-dashboard-in-sap-digital-manufacturing-in-5-steps](https://blog.concircle.com/en/how-to-create-a-dashboard-in-sap-digital-manufacturing-in-5-steps)  
45. Unified Operations Center \- AVEVA Select California, 3월 14, 2026에 액세스, [https://california.avevaselect.com/media/ASCA/presentations/AVEVA2020LIVE\!/UOC\_Michelle.pdf](https://california.avevaselect.com/media/ASCA/presentations/AVEVA2020LIVE!/UOC_Michelle.pdf)  
46. AVEVA™ Unified Operations Center for Data Centers, 3월 14, 2026에 액세스, [https://www.aveva.com/en/products/unified-operations-center-for-data-centers/](https://www.aveva.com/en/products/unified-operations-center-for-data-centers/)  
47. Welcome to AVEVA™ Unified Operations Center (UOC) for Water, 3월 14, 2026에 액세스, [https://docs.aveva.com/bundle/uoc-for-water/page/1345544.html](https://docs.aveva.com/bundle/uoc-for-water/page/1345544.html)  
48. AVEVA Unified Operations Center \- Educational Videos, 3월 14, 2026에 액세스, [https://industrial-software.com/training-support/educational-videos-by-product/aveva-unified-operations-center/](https://industrial-software.com/training-support/educational-videos-by-product/aveva-unified-operations-center/)  
49. Manufacturing Execution System (MES) / MOM Software \- Plex Systems, 3월 14, 2026에 액세스, [https://plex.rockwellautomation.com/en-us/products/manufacturing-execution-system.html](https://plex.rockwellautomation.com/en-us/products/manufacturing-execution-system.html)  
50. Plex MES for Food & Beverage | FactoryTalk | US \- Rockwell Automation, 3월 14, 2026에 액세스, [https://www.rockwellautomation.com/en-us/products/software/factorytalk/operationsuite/mes/plex-mes/plex-mes-for-food-and-beverage.html](https://www.rockwellautomation.com/en-us/products/software/factorytalk/operationsuite/mes/plex-mes/plex-mes-for-food-and-beverage.html)  
51. Plex MES for Automotive | Rockwell Automation, 3월 14, 2026에 액세스, [https://plex.rockwellautomation.com/en-us/resources/plex-mes-automotive.html](https://plex.rockwellautomation.com/en-us/resources/plex-mes-automotive.html)  
52. Dashboard Design UX Patterns Best Practices \- Pencil & Paper, 3월 14, 2026에 액세스, [https://www.pencilandpaper.io/articles/ux-pattern-analysis-data-dashboards](https://www.pencilandpaper.io/articles/ux-pattern-analysis-data-dashboards)  
53. Predictive Maintenance Dashboards: 5 Proven Steps in Power BI \- Sparity, 3월 14, 2026에 액세스, [https://www.sparity.com/blogs/predictive-maintenance-dashboard/](https://www.sparity.com/blogs/predictive-maintenance-dashboard/)  
54. Quality Dashboards \- Advantive, 3월 14, 2026에 액세스, [https://www.advantive.com/solutions/spc-software/spc-manufacturing/quality-dashboards/](https://www.advantive.com/solutions/spc-software/spc-manufacturing/quality-dashboards/)  
55. SAP Digital Manufacturing (SAP DM) to digitalize your shop floor \- ORBIS America, 3월 14, 2026에 액세스, [https://www.orbisusa.com/en-us/sap-consulting/supply-chain-management/sap-dm.html](https://www.orbisusa.com/en-us/sap-consulting/supply-chain-management/sap-dm.html)  
56. Manufacturing Execution Systems (MES) \- Rockwell Automation, 3월 14, 2026에 액세스, [https://www.rockwellautomation.com/en-us/products/software/factorytalk/operationsuite/mes.html](https://www.rockwellautomation.com/en-us/products/software/factorytalk/operationsuite/mes.html)  
57. Opcenter Execution Process \- Siemens, 3월 14, 2026에 액세스, [https://www.siemens.com/en-us/products/opcenter/execution/process/](https://www.siemens.com/en-us/products/opcenter/execution/process/)  
58. Opcenter Execution Medical Device MES \- Siemens, 3월 14, 2026에 액세스, [https://www.siemens.com/en-us/products/opcenter/execution/medical-device/](https://www.siemens.com/en-us/products/opcenter/execution/medical-device/)  
59. Execute — Siemens Opcenter MoM (MES · APS · Insights Hub) \- Connected Manufacturing, 3월 14, 2026에 액세스, [https://www.connectedmanufacturing.com/execute](https://www.connectedmanufacturing.com/execute)  
60. 3 OEE Dashboard Templates for Smarter Manufacturing \- dataPARC, 3월 14, 2026에 액세스, [https://www.dataparc.com/blog/oee-dashboard-templates-for-smarter-manufacturing/](https://www.dataparc.com/blog/oee-dashboard-templates-for-smarter-manufacturing/)  
61. Using Pareto Charts For Quality Control \- dataPARC, 3월 14, 2026에 액세스, [https://www.dataparc.com/blog/using-pareto-charts-for-quality-control/](https://www.dataparc.com/blog/using-pareto-charts-for-quality-control/)  
62. Plex Production Monitoring Demo \- Rockwell Automation, 3월 14, 2026에 액세스, [https://www.rockwellautomation.com/content/plex/global/en/resources/plex-production-monitoring-demo.html](https://www.rockwellautomation.com/content/plex/global/en/resources/plex-production-monitoring-demo.html)  
63. Sankey Diagram Explained: Examples, Uses, and How It Works \- Domo, 3월 14, 2026에 액세스, [https://www.domo.com/learn/charts/sankey-diagrams](https://www.domo.com/learn/charts/sankey-diagrams)  
64. Sankey Diagrams: Flow Visualization Masterclass \- Think Design, 3월 14, 2026에 액세스, [https://think.design/services/data-visualization-data-design/sankey-diagram/](https://think.design/services/data-visualization-data-design/sankey-diagram/)  
65. Material Flow Diagram \- Samples & Software | e\!Sankey \- iPoint-systems, 3월 14, 2026에 액세스, [https://www.ipoint-systems.com/software/e-sankey/material-flow-diagram/](https://www.ipoint-systems.com/software/e-sankey/material-flow-diagram/)  
66. Sankey Diagram: Visualize & Optimize Industrial Energy Flows \- Wattnow, 3월 14, 2026에 액세스, [https://wattnow.io/2026/01/21/sankey-diagram-visualize-optimize-industrial-energy-flows/](https://wattnow.io/2026/01/21/sankey-diagram-visualize-optimize-industrial-energy-flows/)  
67. AVEVA Screen Capture and Print \- AVEVA™ Documentation, 3월 14, 2026에 액세스, [https://docs.aveva.com/bundle/uoc-content-library/page/928198.html](https://docs.aveva.com/bundle/uoc-content-library/page/928198.html)  
68. View WS Corporate dashboard \- AVEVA™ Documentation, 3월 14, 2026에 액세스, [https://docs.aveva.com/bundle/uoc-for-water/page/1364618.html](https://docs.aveva.com/bundle/uoc-for-water/page/1364618.html)  
69. Dashboards \- Enact Online Help, 3월 14, 2026에 액세스, [https://enacthelp.infinityqs.com/en-us/Dashboards/IntroDashboards.htm](https://enacthelp.infinityqs.com/en-us/Dashboards/IntroDashboards.htm)  
70. SPC Pareto Chart \- Perspective \- Sepasoft Documentation Portal, 3월 14, 2026에 액세스, [https://docs.sepasoft.com/articles/user-manual/spc-pareto-chart-perspective](https://docs.sepasoft.com/articles/user-manual/spc-pareto-chart-perspective)  
71. Pareto Chart \- Advantive, 3월 14, 2026에 액세스, [https://www.advantive.com/solutions/spc-software/spc-chart-guide/pareto-chart/](https://www.advantive.com/solutions/spc-software/spc-chart-guide/pareto-chart/)  
72. Quick Start for Proficy Operations Hub from GE Digital \- HANNOVER MESSE, 3월 14, 2026에 액세스, [https://www.hannovermesse.de/apollo/hannover\_messe\_2023/obs/Binary/A1252183/quick-start-for-proficy-operations-hub-2021-from-ge-digital.pdf](https://www.hannovermesse.de/apollo/hannover_messe_2023/obs/Binary/A1252183/quick-start-for-proficy-operations-hub-2021-from-ge-digital.pdf)  
73. Designing a KPI Dashboard for OEE: A Practical Guide \- TEEPTRAK \- Connect to your industrial potential, 3월 14, 2026에 액세스, [https://teeptrak.com/en/designing-a-kpi-dashboard-for-oee-a-practical-guide/](https://teeptrak.com/en/designing-a-kpi-dashboard-for-oee-a-practical-guide/)  
74. How to Automate Visual QC Inspections Effectively | Cognex, 3월 14, 2026에 액세스, [https://www.cognex.com/en/tools-and-resources/resource-center/seeing-what-humans-miss-how-ai-powered-vision-systems-are-redefining-quality-control](https://www.cognex.com/en/tools-and-resources/resource-center/seeing-what-humans-miss-how-ai-powered-vision-systems-are-redefining-quality-control)  
75. Proficy Operations Hub \- Com-Forth, 3월 14, 2026에 액세스, [https://info.comforth.hu/en/proficy-operations-hub?hsLang=en](https://info.comforth.hu/en/proficy-operations-hub?hsLang=en)  
76. OEE Dashboards and Reports for Production \- manubes, 3월 14, 2026에 액세스, [https://www.manubes.com/oee-visualization/](https://www.manubes.com/oee-visualization/)  
77. smart factory dashboard \- operation visualization & oee monitoring, 3월 14, 2026에 액세스, [https://www.fujitsu.com/th/en/imagesgig5/Smart-Factory-Dashboard.pdf](https://www.fujitsu.com/th/en/imagesgig5/Smart-Factory-Dashboard.pdf)  
78. Enact by InfinityQS: Cloud-Based SPC for Smarter Manufacturing \- Advantive, 3월 14, 2026에 액세스, [https://www.advantive.com/products/infinity-qs-enact/](https://www.advantive.com/products/infinity-qs-enact/)  
79. Honeywell Forge for Buildings \- Site Manager User Guide, 3월 14, 2026에 액세스, [https://prod-edam.honeywell.com/content/dam/honeywell-edam/hbt/en-us/documents/manuals-and-guides/user-manuals/hon-ba-hbs-honeywell-forge-for-buildings-site-manager-user-guide-31-00868-2.pdf?download=false](https://prod-edam.honeywell.com/content/dam/honeywell-edam/hbt/en-us/documents/manuals-and-guides/user-manuals/hon-ba-hbs-honeywell-forge-for-buildings-site-manager-user-guide-31-00868-2.pdf?download=false)  
80. AI-Powered Predictive Maintenance for Smarter Equipment Health | Innovapptive, 3월 14, 2026에 액세스, [https://www.innovapptive.com/product/maintenance-suite/maintenance-insights](https://www.innovapptive.com/product/maintenance-suite/maintenance-insights)  
81. Ignition Community Conference Archives \- 2019 \- Inductive Automation, 3월 14, 2026에 액세스, [https://icc.inductiveautomation.com/archive/videos/2019/discover-gallery](https://icc.inductiveautomation.com/archive/videos/2019/discover-gallery)  
82. Cognex VisionPro ViDi Help \- Getting Started \- Documentation, 3월 14, 2026에 액세스, [https://docs.cognex.com/vidi\_341/web/EN/vidisuite/Default.htm](https://docs.cognex.com/vidi_341/web/EN/vidisuite/Default.htm)  
83. A Guide to Predictive Maintenance Software for Manufacturing \- Tractian, 3월 14, 2026에 액세스, [https://tractian.com/en/blog/a-guide-to-predictive-maintenance-software-for-manufacturing](https://tractian.com/en/blog/a-guide-to-predictive-maintenance-software-for-manufacturing)  
84. Improve manufacturing quality control with Visual Inspection AI | Google Cloud Blog, 3월 14, 2026에 액세스, [https://cloud.google.com/blog/products/ai-machine-learning/improve-manufacturing-quality-control-with-visual-inspection-ai](https://cloud.google.com/blog/products/ai-machine-learning/improve-manufacturing-quality-control-with-visual-inspection-ai)  
85. Vision Sensor with Built-in AI \- IV3 series | KEYENCE America, 3월 14, 2026에 액세스, [https://www.keyence.com/products/vision/vision-sensor/iv3/](https://www.keyence.com/products/vision/vision-sensor/iv3/)  
86. In-Sight ViDi User Interface \- Documentation | Cognex, 3월 14, 2026에 액세스, [https://support.cognex.com/docs/isvidi\_130/web/EN/Help\_ISViDi/Content/Topics/IDE/in-sight-vidi-ui.htm?TocPath=In-Sight%20ViDi%20User%20Interface|\_\_\_\_\_0](https://support.cognex.com/docs/isvidi_130/web/EN/Help_ISViDi/Content/Topics/IDE/in-sight-vidi-ui.htm?TocPath=In-Sight+ViDi+User+Interface%7C_____0)  
87. AI Inspection Systems for Manufacturing: Complete 2025 Guide, 3월 14, 2026에 액세스, [https://www.overview.ai/blog/ai-inspection-systems-manufacturing/](https://www.overview.ai/blog/ai-inspection-systems-manufacturing/)  
88. HMI Design Guide: Human-Machine Interface Explained \[2026\] \- Eleken, 3월 14, 2026에 액세스, [https://www.eleken.co/blog-posts/human-machine-interface-design](https://www.eleken.co/blog-posts/human-machine-interface-design)  
89. AI Visual Inspection for Defect Detection in Manufacturing \- Miquido, 3월 14, 2026에 액세스, [https://www.miquido.com/custom-ai-solutions/visual-inspection-manufacturing/](https://www.miquido.com/custom-ai-solutions/visual-inspection-manufacturing/)  
90. SAP Digital Manufacturing | Features, 3월 14, 2026에 액세스, [https://www.sap.com/products/scm/digital-manufacturing/features.html](https://www.sap.com/products/scm/digital-manufacturing/features.html)  
91. Opcenter Intelligence | Siemens, 3월 14, 2026에 액세스, [https://www.siemens.com/en-us/products/opcenter/manufacturing-intelligence/](https://www.siemens.com/en-us/products/opcenter/manufacturing-intelligence/)  
92. MES For Dummies®, Plex Systems Inc., 2nd Special Edition \- Rockwell Automation, 3월 14, 2026에 액세스, [https://literature.rockwellautomation.com/idc/groups/literature/documents/br/plex-br023\_-en-p.pdf](https://literature.rockwellautomation.com/idc/groups/literature/documents/br/plex-br023_-en-p.pdf)