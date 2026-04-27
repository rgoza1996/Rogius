'use client'

export type SecurityLevel = 'auto' | 'confirm-destructive' | 'always-confirm'

// Patterns that indicate potentially destructive operations
const DESTRUCTIVE_PATTERNS = [
  // File deletion
  /\brm\s+(-rf?|-fr?|\s+-\w*[rf]|\s+-\w*f\w*r)/i,
  /\bdel\s+\/f/i,
  /\berase\s+/i,
  /\bRemove-Item\s+/i,
  
  // Disk operations
  /\bformat\s+/i,
  /\bdiskpart/i,
  /\bmkfs\./i,
  /\bnew-fs/i,
  
  // Network downloads piped to shell
  /curl.*\|.*(sh|bash|powershell)/i,
  /wget.*\|.*(sh|bash|powershell)/i,
  /Invoke-WebRequest.*\|.*(iex|Invoke-Expression)/i,
  
  // Registry modifications
  /\breg\s+(delete|add)\s+/i,
  /\bSet-ItemProperty\s+.*Registry/i,
  /\bRemove-ItemProperty\s+.*Registry/i,
  
  // Service/process termination
  /\bkill\s+-9/i,
  /\btaskkill\s+\/f/i,
  /\bStop-Process\s+-Force/i,
  /\bsc\s+(delete|stop|config)/i,
  
  // Permission changes
  /\bchmod\s+.*777/i,
  /\btakeown\s+/i,
  /\bicacls\s+.*\/grant/i,
  
  // System modifications
  /\bsfc\s+\/scannow/i,
  /\bdism\s+/i,
  /\bschtasks\s+\/delete/i,
  
  // Script execution with elevated permissions
  /\bsudo\s/i,
  /\brunas\s+/i,
  /\bStart-Process\s+.*-Verb\s+runAs/i,
]

// Patterns for read-only safe commands
const SAFE_PATTERNS = [
  /^\s*(dir|ls|echo|cat|type|findstr|grep|head|tail|wc|pwd|cd|pushd|popd|clear|cls|date|time|whoami|hostname|ver|systeminfo|get-wmiobject|get-process|get-service)\s/i,
  /^\s*git\s+(status|log|show|branch|remote|diff)\s/i,
  /^\s*npm\s+list\s/i,
]

export function isDestructiveCommand(command: string): boolean {
  const trimmed = command.trim().toLowerCase()
  
  // First check if it's explicitly safe
  if (SAFE_PATTERNS.some(pattern => pattern.test(trimmed))) {
    return false
  }
  
  // Check for destructive patterns
  return DESTRUCTIVE_PATTERNS.some(pattern => pattern.test(trimmed))
}

export function shouldConfirmCommand(
  command: string,
  securityLevel: SecurityLevel
): boolean {
  switch (securityLevel) {
    case 'auto':
      return false
    
    case 'confirm-destructive':
      return isDestructiveCommand(command)
    
    case 'always-confirm':
      return true
    
    default:
      return true
  }
}

export function getSecurityDescription(level: SecurityLevel): string {
  switch (level) {
    case 'auto':
      return 'Execute all commands automatically (fast but risky)'
    case 'confirm-destructive':
      return 'Confirm only potentially dangerous commands (recommended)'
    case 'always-confirm':
      return 'Confirm every command before execution (safest)'
    default:
      return 'Unknown security level'
  }
}

export function categorizeCommand(command: string): {
  isDestructive: boolean
  category: 'safe' | 'caution' | 'destructive' | 'unknown'
  reason?: string
} {
  const trimmed = command.trim().toLowerCase()
  
  // Check if explicitly safe
  if (SAFE_PATTERNS.some(pattern => pattern.test(trimmed))) {
    return {
      isDestructive: false,
      category: 'safe',
      reason: 'Read-only operation'
    }
  }
  
  // Check for destructive patterns
  const matchingPattern = DESTRUCTIVE_PATTERNS.find(pattern => pattern.test(trimmed))
  if (matchingPattern) {
    // Determine specific reason
    let reason = 'Potentially destructive operation'
    if (trimmed.includes('rm') || trimmed.includes('del') || trimmed.includes('remove-item')) {
      reason = 'File deletion command'
    } else if (trimmed.includes('format') || trimmed.includes('diskpart')) {
      reason = 'Disk formatting operation'
    } else if (trimmed.includes('curl') || trimmed.includes('wget') || trimmed.includes('invoke-webrequest')) {
      reason = 'Download and execute pattern'
    } else if (trimmed.includes('reg') || trimmed.includes('registry')) {
      reason = 'Registry modification'
    } else if (trimmed.includes('kill') || trimmed.includes('taskkill') || trimmed.includes('stop-process')) {
      reason = 'Process termination'
    } else if (trimmed.includes('sudo') || trimmed.includes('runas')) {
      reason = 'Elevated privilege execution'
    }
    
    return {
      isDestructive: true,
      category: 'destructive',
      reason
    }
  }
  
  return {
    isDestructive: false,
    category: 'unknown',
    reason: 'Command not in safe or destructive lists'
  }
}

export interface SecurityResult {
  shouldConfirm: boolean
  category: 'safe' | 'caution' | 'destructive' | 'unknown'
  reason?: string
}

export function checkSecurity(command: string, level: SecurityLevel): SecurityResult {
  const category = categorizeCommand(command)
  return {
    shouldConfirm: shouldConfirmCommand(command, level),
    category: category.category,
    reason: category.reason
  }
}
