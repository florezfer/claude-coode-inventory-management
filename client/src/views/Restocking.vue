<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.budget') }}</h3>
          <span v-if="recalculating" class="recalculating">{{ t('restocking.recalculating') }}</span>
        </div>
        <div class="budget-body">
          <div class="budget-value">{{ formatCurrency(budget) }}</div>
          <input
            v-model.number="budget"
            type="range"
            class="budget-slider"
            :min="BUDGET_MIN"
            :max="BUDGET_MAX"
            :step="BUDGET_STEP"
            :aria-label="t('restocking.budget')"
          >
          <div class="budget-scale">
            <span>{{ formatCurrency(BUDGET_MIN) }}</span>
            <span>{{ formatCurrency(BUDGET_MAX) }}</span>
          </div>
          <p class="budget-hint">{{ t('restocking.budgetHint') }}</p>
        </div>
      </div>

      <div class="stats-grid">
        <div class="stat-card info">
          <div class="stat-label">{{ t('restocking.budget') }}</div>
          <div class="stat-value">{{ formatCurrency(plan.budget) }}</div>
        </div>
        <div class="stat-card warning">
          <div class="stat-label">{{ t('restocking.totalCost') }}</div>
          <div class="stat-value">{{ formatCurrency(plan.total_cost) }}</div>
        </div>
        <div class="stat-card success">
          <div class="stat-label">{{ t('restocking.remaining') }}</div>
          <div class="stat-value">{{ formatCurrency(plan.remaining_budget) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('restocking.itemsRecommended') }}</div>
          <div class="stat-value">{{ plan.items.length }}</div>
        </div>
      </div>

      <div v-if="submittedOrder" class="order-success">
        <span class="order-success-text">
          {{ t('restocking.orderPlaced', { orderNumber: submittedOrder.order_number }) }}
        </span>
        <router-link to="/orders" class="order-success-link">
          {{ t('restocking.viewInOrders') }}
        </router-link>
      </div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">
            {{ t('restocking.recommendations') }} ({{ plan.items.length }})
          </h3>
          <button
            class="place-order-btn"
            :disabled="!canPlaceOrder"
            @click="placeOrder"
          >
            {{ submitting ? t('restocking.placingOrder') : t('restocking.placeOrder') }}
          </button>
        </div>

        <div v-if="plan.items.length === 0" class="empty-state">
          <p>{{ t('restocking.noRecommendations') }}</p>
        </div>
        <div v-else class="table-container">
          <table>
            <thead>
              <tr>
                <th>{{ t('restocking.table.sku') }}</th>
                <th>{{ t('restocking.table.itemName') }}</th>
                <th>{{ t('restocking.table.category') }}</th>
                <th class="numeric">{{ t('restocking.table.onHand') }}</th>
                <th class="numeric">{{ t('restocking.table.forecast') }}</th>
                <th class="numeric">{{ t('restocking.table.shortfall') }}</th>
                <th class="numeric">{{ t('restocking.table.quantity') }}</th>
                <th class="numeric">{{ t('restocking.table.unitCost') }}</th>
                <th class="numeric">{{ t('restocking.table.lineCost') }}</th>
                <th>{{ t('restocking.table.coverage') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in plan.items" :key="item.sku">
                <td><strong>{{ item.sku }}</strong></td>
                <td>{{ translateProductName(item.name) }}</td>
                <td>{{ translateCategory(item.category) }}</td>
                <td class="numeric">{{ item.quantity_on_hand.toLocaleString() }}</td>
                <td class="numeric">{{ item.forecasted_demand.toLocaleString() }}</td>
                <td class="numeric shortfall">{{ item.shortfall.toLocaleString() }}</td>
                <td class="numeric"><strong>{{ item.recommended_quantity.toLocaleString() }}</strong></td>
                <td class="numeric">{{ formatCost(item.unit_cost) }}</td>
                <td class="numeric"><strong>{{ formatCost(item.line_cost) }}</strong></td>
                <td>
                  <span :class="['badge', item.fully_funded ? 'success' : 'warning']">
                    {{ item.fully_funded ? t('restocking.fullyFunded') : t('restocking.partiallyFunded') }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, watch, onUnmounted } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'
import { formatCurrency as format, formatCurrencyWithDecimals } from '../utils/currency'

const BUDGET_MIN = 0
const BUDGET_MAX = 100000
const BUDGET_STEP = 1000
const DEBOUNCE_MS = 300

export default {
  name: 'Restocking',
  setup() {
    const { t, currentCurrency, translateProductName } = useI18n()

    const loading = ref(true)
    const recalculating = ref(false)
    const submitting = ref(false)
    const error = ref(null)
    const budget = ref(25000)
    const plan = ref({ budget: 0, total_cost: 0, remaining_budget: 0, items: [] })
    const submittedOrder = ref(null)

    let debounceHandle = null

    // Budgets and costs are held in USD; display converts for the active locale
    const formatCurrency = (amount) => format(amount, currentCurrency.value)
    // Unit and line costs carry cents, which formatCurrency would round away
    const formatCost = (amount) => formatCurrencyWithDecimals(amount, currentCurrency.value, 2)

    const translateCategory = (category) => {
      const categoryMap = {
        'Circuit Boards': t('categories.circuitBoards'),
        'Sensors': t('categories.sensors'),
        'Actuators': t('categories.actuators'),
        'Controllers': t('categories.controllers'),
        'Power Supplies': t('categories.powerSupplies')
      }
      return categoryMap[category] || category
    }

    const canPlaceOrder = computed(() => plan.value.items.length > 0 && !submitting.value)

    const loadRecommendations = async (isInitial = false) => {
      try {
        if (isInitial) {
          loading.value = true
        } else {
          recalculating.value = true
        }
        error.value = null
        plan.value = await api.getRestockingRecommendations(budget.value)
      } catch (err) {
        error.value = 'Failed to load restocking recommendations: ' + err.message
      } finally {
        loading.value = false
        recalculating.value = false
      }
    }

    const placeOrder = async () => {
      if (!canPlaceOrder.value) return

      try {
        submitting.value = true
        error.value = null
        const items = plan.value.items.map(item => ({
          sku: item.sku,
          quantity: item.recommended_quantity
        }))
        submittedOrder.value = await api.createRestockingOrder(items)
      } catch (err) {
        error.value = 'Failed to place restocking order: ' + err.message
      } finally {
        submitting.value = false
      }
    }

    // The slider fires continuously while dragging, so settle before calling
    watch(budget, () => {
      submittedOrder.value = null
      clearTimeout(debounceHandle)
      debounceHandle = setTimeout(() => loadRecommendations(), DEBOUNCE_MS)
    })

    onMounted(() => loadRecommendations(true))
    onUnmounted(() => clearTimeout(debounceHandle))

    return {
      t,
      BUDGET_MIN,
      BUDGET_MAX,
      BUDGET_STEP,
      loading,
      recalculating,
      submitting,
      error,
      budget,
      plan,
      submittedOrder,
      canPlaceOrder,
      formatCurrency,
      formatCost,
      translateCategory,
      translateProductName,
      placeOrder
    }
  }
}
</script>

<style scoped>
.budget-body {
  padding: 1.5rem;
}

.budget-value {
  font-size: 2rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.02em;
  margin-bottom: 1rem;
}

.budget-slider {
  width: 100%;
  accent-color: #3b82f6;
  cursor: pointer;
}

.budget-scale {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  color: #94a3b8;
  margin-top: 0.5rem;
}

.budget-hint {
  font-size: 0.813rem;
  color: #64748b;
  margin: 0.75rem 0 0;
}

.recalculating {
  font-size: 0.813rem;
  color: #64748b;
}

.place-order-btn {
  padding: 0.5rem 1.25rem;
  border: none;
  border-radius: 6px;
  font-size: 0.813rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
  background: #3b82f6;
  color: white;
}

.place-order-btn:hover:not(:disabled) {
  background: #2563eb;
  transform: translateY(-1px);
  box-shadow: 0 2px 4px rgba(59, 130, 246, 0.3);
}

.place-order-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.order-success {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.875rem 1.25rem;
  margin-bottom: 1.5rem;
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  border-left: 3px solid #16a34a;
  border-radius: 8px;
}

.order-success-text {
  font-size: 0.875rem;
  font-weight: 600;
  color: #166534;
}

.order-success-link {
  font-size: 0.875rem;
  font-weight: 600;
  color: #2563eb;
  white-space: nowrap;
}

.empty-state {
  padding: 2.5rem 1.5rem;
  text-align: center;
  color: #64748b;
  font-size: 0.875rem;
}

.empty-state p {
  margin: 0;
}

.numeric {
  text-align: right;
}

.shortfall {
  color: #b45309;
  font-weight: 600;
}
</style>
