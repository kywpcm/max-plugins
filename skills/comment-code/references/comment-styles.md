# 언어별 주석 문법 및 예시 가이드

## 문법 요약

| 언어 | Doc 주석 | 인라인 | 섹션 구분 |
|------|----------|--------|-----------|
| JS/TS | `/** @param @returns */` | `// 설명` | `// === Section ===` |
| JSX/TSX | `/** @component @returns */` | `// 설명` 또는 `{/* 설명 */}` (JSX 내부) | `// === Section ===` |
| HTML | N/A | `<!-- 설명 -->` | `<!-- ===== Section ===== -->` |
| Java | `/** @param @return @throws */` | `// 설명` | `// ========== Section ==========` |
| Python | `"""docstring"""` | `# 설명` | `# === Section ===` |
| CSS/SCSS | `/** */` | `/* 설명 */` | `/* === Section === */` |
| YAML | N/A | `# 설명` | `# === Section ===` |

---

## JavaScript / TypeScript

### Doc 주석

```javascript
/**
 * 상품 목록을 가격 범위로 필터링한다.
 * @param {Array<Product>} products - 전체 상품 목록
 * @param {number} minPrice - 최소 가격 (포함)
 * @param {number} maxPrice - 최대 가격 (포함)
 * @returns {Array<Product>} 가격 범위에 해당하는 상품 목록
 */
export function filterByPriceRange(products, minPrice, maxPrice) {
  return products.filter(p => p.price >= minPrice && p.price <= maxPrice);
}
```

```typescript
/**
 * API 응답을 캐시에 저장하고, 만료 시간이 지나면 자동으로 갱신한다.
 * @param {string} key - 캐시 키
 * @param {() => Promise<T>} fetcher - 데이터를 가져오는 비동기 함수
 * @param {number} ttl - 캐시 유효 시간 (밀리초)
 * @returns {Promise<T>} 캐시된 데이터 또는 새로 가져온 데이터
 */
async function getCachedData<T>(key: string, fetcher: () => Promise<T>, ttl: number): Promise<T> {
  // ...
}
```

### 인라인 주석

```javascript
// 쿠폰 할인은 최종 결제 금액의 50%를 초과할 수 없다 (정책 제한)
const maxDiscount = totalPrice * 0.5;

// 서버 시간 기준으로 이벤트 종료 여부를 판단한다 (클라이언트 시간 조작 방지)
const isExpired = serverTime > event.endDate;

// URL의 쿼리 파라미터에서 UTM 태그를 추출한다
const utmSource = /[?&]utm_source=([^&]+)/.exec(location.search)?.[1];
```

### 섹션 구분

```javascript
// === 상수 정의 ===
const API_BASE_URL = '/api/v2';
const MAX_RETRY_COUNT = 3;

// === 유틸리티 함수 ===
function formatCurrency(amount) { ... }
function parseQueryString(url) { ... }

// === API 호출 ===
async function fetchProducts() { ... }
async function updateCart(items) { ... }
```

---

## JSX / TSX

### Doc 주석

```jsx
/**
 * 상품 카드 컴포넌트.
 * 상품 이미지, 이름, 가격, 할인 정보를 표시한다.
 * @component
 * @param {Object} props
 * @param {Product} props.product - 상품 정보 객체
 * @param {boolean} props.isWished - 위시리스트 포함 여부
 * @param {(id: string) => void} props.onToggleWish - 위시리스트 토글 핸들러
 * @returns {JSX.Element}
 */
const ProductCard = ({ product, isWished, onToggleWish }) => {
  // ...
};
```

### JSX 내부 주석 (반드시 `{/* */}` 사용)

```jsx
return (
  <div className="product-list">
    {/* 상품이 없을 때 빈 상태 안내 메시지 */}
    {products.length === 0 && <EmptyState />}

    {/* 상품 그리드 - 한 줄에 최대 3개 표시 */}
    <div className="grid">
      {products.map(product => (
        <ProductCard key={product.id} product={product} />
      ))}
    </div>

    {/* 무한 스크롤 감지용 관찰 대상 요소 */}
    <div ref={observerRef} />
  </div>
);
```

### JSX 외부 주석 (일반 `//` 사용)

```jsx
const ProductList = ({ products }) => {
  // === State 관리 ===
  const [sortBy, setSortBy] = useState('latest');
  const observerRef = useRef(null);

  // === Side Effects ===
  // 스크롤 위치 복원을 위해 마운트 시 이전 위치로 이동
  useEffect(() => {
    window.scrollTo(0, savedScrollPosition);
  }, []);

  // === 렌더링 ===
  return ( ... );
};
```

---

## HTML

### 인라인 주석

```html
<!-- 로그인 상태에 따라 표시되는 영역 -->
<div id="user-menu">
  <!-- 프로필 이미지: CDN에서 로드, 실패 시 기본 이미지 표시 -->
  <img src="/profile.jpg" onerror="this.src='/default.png'" />
</div>
```

### 섹션 구분

```html
<!-- ===== Header Section ===== -->
<header>
  <nav>...</nav>
</header>

<!-- ===== Main Content ===== -->
<main>
  <!-- 상품 목록 영역 -->
  <section class="products">...</section>

  <!-- 추천 상품 영역 (개인화 API 기반) -->
  <section class="recommendations">...</section>
</main>

<!-- ===== Footer Section ===== -->
<footer>...</footer>
```

### script/style 내부

```html
<script>
  // 페이지 로드 완료 후 분석 스크립트를 초기화한다
  window.addEventListener('load', () => {
    initAnalytics();
  });
</script>

<style>
  /* 모바일 환경에서 사이드바를 숨긴다 */
  @media (max-width: 768px) {
    .sidebar { display: none; }
  }
</style>
```

---

## Java

### Doc 주석

```java
/**
 * 주문 금액에 대한 할인을 계산한다.
 * 쿠폰 할인, 등급 할인, 프로모션 할인을 순차적으로 적용한다.
 *
 * @param order 주문 정보
 * @param coupon 적용할 쿠폰 (null 가능)
 * @param memberGrade 회원 등급
 * @return 최종 할인 금액
 * @throws InvalidCouponException 쿠폰이 만료되었거나 사용 조건에 맞지 않는 경우
 */
public int calculateDiscount(Order order, Coupon coupon, MemberGrade memberGrade) {
    // ...
}
```

```java
/**
 * 상품 카탈로그 서비스.
 * 상품 조회, 검색, 카테고리 관리 등의 기능을 제공한다.
 */
@Service
public class CatalogService {
    // ...
}
```

### 인라인 주석

```java
// 재고가 0 이하인 상품은 판매 불가로 처리한다
if (product.getStock() <= 0) {
    product.setStatus(ProductStatus.SOLD_OUT);
}

// 동시성 제어를 위해 비관적 락을 사용한다 (재고 차감 시 경합 방지)
@Lock(LockModeType.PESSIMISTIC_WRITE)
Optional<Product> findByIdForUpdate(Long id);
```

### 섹션 구분

```java
// ========== 필드 ==========
private final ProductRepository productRepository;
private final CacheManager cacheManager;

// ========== 생성자 ==========
public CatalogService(ProductRepository productRepository, CacheManager cacheManager) {
    this.productRepository = productRepository;
    this.cacheManager = cacheManager;
}

// ========== Public 메서드 ==========
public Product findById(Long id) { ... }
public List<Product> search(String keyword) { ... }

// ========== Private 메서드 ==========
private void validateProduct(Product product) { ... }
```

---

## Python

### Doc 주석 (docstring)

```python
def calculate_shipping_fee(weight: float, distance: int, is_fragile: bool) -> int:
    """배송비를 계산한다.

    무게, 거리, 파손 위험 여부를 고려하여 최종 배송비를 산출한다.
    제주/도서 지역은 추가 요금이 부과된다.

    Args:
        weight: 상품 무게 (kg)
        distance: 배송 거리 (km)
        is_fragile: 파손 위험 상품 여부

    Returns:
        최종 배송비 (원)

    Raises:
        ValueError: 무게가 음수이거나 거리가 0 이하인 경우
    """
    ...
```

### 인라인 주석

```python
# 주문 취소는 결제 후 24시간 이내에만 가능하다
if (now - order.paid_at).total_seconds() > 86400:  # 24시간 = 86400초
    raise CancelTimeExceededException()

# 할인율은 소수점 이하 버림 처리한다 (고객 유리 원칙)
discount_rate = math.floor(raw_rate * 100) / 100
```

### 섹션 구분

```python
# === 상수 ===
MAX_CART_ITEMS = 100
FREE_SHIPPING_THRESHOLD = 30000

# === 헬퍼 함수 ===
def _validate_quantity(quantity: int) -> None:
    ...

# === 메인 로직 ===
def process_order(order: Order) -> Receipt:
    ...
```

---

## CSS / SCSS

### Doc 주석

```css
/**
 * 상품 카드 레이아웃.
 * 그리드 시스템 기반으로 반응형 배치를 처리한다.
 * 모바일: 1열, 태블릿: 2열, 데스크탑: 3열
 */
.product-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}
```

### 인라인 주석

```css
.modal-overlay {
  position: fixed;
  z-index: 9999; /* 모든 요소 위에 표시되도록 최상위 z-index 사용 */
  background: rgba(0, 0, 0, 0.5); /* 반투명 배경으로 딤 처리 */
}

.truncate {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  /* -webkit-line-clamp은 여러 줄 말줄임에만 사용한다 */
}
```

### 섹션 구분

```css
/* === 리셋 스타일 === */
* { margin: 0; padding: 0; box-sizing: border-box; }

/* === 레이아웃 === */
.container { max-width: 1200px; margin: 0 auto; }
.header { ... }
.footer { ... }

/* === 컴포넌트 === */
.button { ... }
.card { ... }

/* === 유틸리티 === */
.hidden { display: none; }
.sr-only { ... }
```

---

## YAML

### 인라인 주석

```yaml
server:
  port: 8080
  # 개발 환경에서만 graceful shutdown 비활성화
  shutdown: immediate

spring:
  datasource:
    url: jdbc:mysql://localhost:3306/gift
    # HikariCP 커넥션 풀 설정
    hikari:
      maximum-pool-size: 20  # 동시 접속 최대 20개
      connection-timeout: 3000  # 3초 내 커넥션 획득 실패 시 에러
```

### 섹션 구분

```yaml
# === 서버 설정 ===
server:
  port: 8080

# === 데이터베이스 설정 ===
spring:
  datasource:
    url: jdbc:mysql://localhost:3306/gift

# === 캐시 설정 ===
spring:
  redis:
    host: localhost
    port: 6379
```
