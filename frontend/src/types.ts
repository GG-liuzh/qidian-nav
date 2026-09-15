export type Scope = 'team' | 'personal'
export type Role = 'member' | 'maintainer' | 'admin'
export type View = Scope | 'favorites' | 'recent'
export interface Workspace { id: string; name: string; public_enabled: boolean; active: boolean; version: number; role: Role }
export interface User {
  id: string
  username: string
  display_name: string
  role: Role | 'personal'
  workspace: Workspace | null
  workspaces: Workspace[]
  is_superadmin: boolean
  csrf_token: string
  is_site_owner: boolean
  has_team: boolean
  has_recovery_code: boolean
  public_profile_url: string
  recovery_code?: string
  preferences: { theme: 'light' | 'dark' | 'system'; layout: 'grid' | 'list'; record_visits: boolean }
}
export interface Category {
  id: string
  scope: Scope
  name: string
  parent_id: string | null
  visibility: 'workspace' | 'restricted'
  sort_order: number
  version: number
  count: number
  can_edit_resources: boolean
}
export interface Environment {
  id: string
  scope: Scope
  key: string
  label: string
  kind: string
  enabled: boolean
  sort_order: number
  version: number
}
export interface Catalog {
  categories: Category[]
  environments: Environment[]
}
export interface Endpoint {
  id: string
  environment_id: string | null
  env_key: string
  env_label: string
  env_kind: string
  url: string
  enabled: boolean
  configured_enabled: boolean
  disabled_reason: string
}
export interface Resource {
  id: string
  scope: Scope
  type: 'system' | 'bookmark'
  name: string
  aliases: string
  description: string
  tags: string[]
  icon: string
  category_id: string | null
  category_name: string
  maintainer_id: string
  maintainer_name: string
  status: 'active' | 'archived'
  version: number
  updated_at: string
  deleted_at: string | null
  endpoints: Endpoint[]
  favorite: boolean
  can_edit: boolean
  can_manage_accounts: boolean
  can_grant: boolean
  is_public: boolean
}
export interface Page<T> {
  items: T[]
  total: number
  next_offset: number | null
}
export type PublicResource = Omit<
  Resource,
  'maintainer_id' | 'status' | 'version' | 'updated_at' | 'deleted_at'
>
export interface Shortcut extends Endpoint {
  resource_id: string
  name: string
  icon: string
  sort_order: number
}
export interface Credential {
  id: string
  endpoint_id: string
  name: string
  username: string | null
  usage_note: string
  status: 'active' | 'pending' | 'disabled' | 'expired'
  expires_at: string | null
  version: number
  can_read: boolean
  can_manage: boolean
  can_grant: boolean
}
export interface Member {
  is_superadmin?: boolean
  id: string
  display_name: string
  username?: string
  role: Role
  active?: boolean
  version?: number
}
export interface ResourceDraft {
  scope: Scope
  type: 'system' | 'bookmark'
  name: string
  category_id: string | null
  aliases: string
  description: string
  tags: string[]
  icon: string
  maintainer_id: string | null
  endpoints: { environment_id: string | null; url: string; enabled: boolean }[]
  status: 'active' | 'archived'
  version?: number
  is_public?: boolean
}
export interface Feedback {
  id: string
  kind: 'add' | 'edit' | 'broken' | 'account'
  title: string
  url: string
  description: string
  status: 'open' | 'accepted' | 'rejected' | 'withdrawn'
  resolution: string
  resource_id: string | null
  category_id: string | null
  version: number
  created_by: string
  creator_name: string
  created_at: string
  can_handle: boolean
}
export const roleNames: Record<Role, string> = {
  member: '普通成员',
  maintainer: '业务维护人',
  admin: '空间管理员',
}
