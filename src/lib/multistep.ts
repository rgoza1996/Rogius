export interface Step {
  id: string
  description: string
  status: 'pending' | 'running' | 'completed' | 'error' | 'skipped'
  result?: string
  error?: string
  dependencies: string[]
  execute: () => Promise<string>
}

export interface MultiStepPlan {
  id: string
  goal: string
  steps: Step[]
  status: 'idle' | 'running' | 'completed' | 'error' | 'cancelled'
  currentStepIndex: number
  startedAt?: number
  completedAt?: number
}

export function createPlan(goal: string, stepConfigs: Omit<Step, 'id' | 'status'>[]): MultiStepPlan {
  return {
    id: `plan-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    goal,
    steps: stepConfigs.map((config, index) => ({
      ...config,
      id: `step-${index}-${Date.now()}`,
      status: 'pending'
    })),
    status: 'idle',
    currentStepIndex: 0
  }
}

export async function executePlan(
  plan: MultiStepPlan,
  onStepStart?: (step: Step, index: number) => void,
  onStepComplete?: (step: Step, index: number, result: string) => void,
  onStepError?: (step: Step, index: number, error: string) => void,
  signal?: AbortSignal
): Promise<MultiStepPlan> {
  if (plan.status === 'running') {
    throw new Error('Plan is already running')
  }

  plan.status = 'running'
  plan.startedAt = Date.now()

  try {
    for (let i = 0; i < plan.steps.length; i++) {
      if (signal?.aborted) {
        plan.status = 'cancelled'
        return plan
      }

      const step = plan.steps[i]
      plan.currentStepIndex = i

      // Check dependencies
      const pendingDeps = step.dependencies.filter(depId => {
        const depStep = plan.steps.find(s => s.id === depId)
        return !depStep || depStep.status !== 'completed'
      })

      if (pendingDeps.length > 0) {
        step.status = 'skipped'
        step.error = `Dependencies not met: ${pendingDeps.join(', ')}`
        onStepError?.(step, i, step.error)
        continue
      }

      // Skip if already completed
      if (step.status === 'completed') {
        continue
      }

      // Execute step
      step.status = 'running'
      onStepStart?.(step, i)

      try {
        const result = await step.execute()
        step.status = 'completed'
        step.result = result
        onStepComplete?.(step, i, result)
      } catch (error) {
        step.status = 'error'
        step.error = error instanceof Error ? error.message : String(error)
        onStepError?.(step, i, step.error)

        // Stop on error unless step has no dependencies (optional)
        if (step.dependencies.length > 0) {
          plan.status = 'error'
          return plan
        }
      }
    }

    plan.status = plan.steps.every(s => s.status === 'completed' || s.status === 'skipped')
      ? 'completed'
      : 'error'
    plan.completedAt = Date.now()

  } catch (error) {
    plan.status = 'error'
    throw error
  }

  return plan
}

export function resetPlan(plan: MultiStepPlan): MultiStepPlan {
  return {
    ...plan,
    status: 'idle',
    currentStepIndex: 0,
    startedAt: undefined,
    completedAt: undefined,
    steps: plan.steps.map(step => ({
      ...step,
      status: 'pending',
      result: undefined,
      error: undefined
    }))
  }
}

export function getPlanProgress(plan: MultiStepPlan): {
  total: number
  completed: number
  running: number
  error: number
  pending: number
  percentage: number
} {
  const total = plan.steps.length
  const completed = plan.steps.filter(s => s.status === 'completed').length
  const running = plan.steps.filter(s => s.status === 'running').length
  const error = plan.steps.filter(s => s.status === 'error').length
  const pending = total - completed - running - error

  return {
    total,
    completed,
    running,
    error,
    pending,
    percentage: Math.round((completed / total) * 100)
  }
}

export function canStepExecute(step: Step, plan: MultiStepPlan): boolean {
  const depsMet = step.dependencies.every(depId => {
    const dep = plan.steps.find(s => s.id === depId)
    return dep?.status === 'completed'
  })
  return depsMet && step.status === 'pending'
}

export function addStepToPlan(
  plan: MultiStepPlan,
  stepConfig: Omit<Step, 'id' | 'status'>,
  afterStepId?: string
): MultiStepPlan {
  const newStep: Step = {
    ...stepConfig,
    id: `step-${plan.steps.length}-${Date.now()}`,
    status: 'pending'
  }

  if (afterStepId) {
    const insertIndex = plan.steps.findIndex(s => s.id === afterStepId)
    if (insertIndex !== -1) {
      plan.steps.splice(insertIndex + 1, 0, newStep)
      return plan
    }
  }

  plan.steps.push(newStep)
  return plan
}
