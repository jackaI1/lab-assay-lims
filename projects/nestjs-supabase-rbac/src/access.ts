import { CanActivate, ExecutionContext, ForbiddenException, Injectable, SetMetadata, UnauthorizedException } from '@nestjs/common';
import { Reflector } from '@nestjs/core';
import { createClient, SupabaseClient, User } from '@supabase/supabase-js';
import { Request } from 'express';

export const permissions = ['patients.read', 'notes.read', 'notes.write', 'appointments.read', 'appointments.write', 'roles.manage', 'audit.read'] as const;
export type Permission = typeof permissions[number];
export const roles = ['admin', 'clinician', 'receptionist', 'patient'] as const;
export const RequirePermission = (permission: Permission) => SetMetadata('permission', permission);
export const Public = () => SetMetadata('public', true);
export interface ClinicRequest extends Request { db: SupabaseClient; user: User }
export function userClient(token: string) {
  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_ANON_KEY;
  if (!url || !key) throw new Error('SUPABASE_URL and SUPABASE_ANON_KEY are required');
  return createClient(url, key, { global: { headers: { Authorization: `Bearer ${token}` } }, auth: { persistSession: false, autoRefreshToken: false } });
}
@Injectable()
export class AccessGuard implements CanActivate {
  constructor(private readonly reflector: Reflector) {}
  async canActivate(context: ExecutionContext) {
    if (this.reflector.getAllAndOverride('public', [context.getHandler(), context.getClass()])) return true;
    const req = context.switchToHttp().getRequest<ClinicRequest>();
    const match = /^Bearer ([^\s]+)$/.exec(req.headers.authorization ?? '');
    if (!match) throw new UnauthorizedException('A Supabase access token is required');
    req.db = userClient(match[1]);
    const { data, error } = await req.db.auth.getUser(match[1]);
    if (error || !data.user) throw new UnauthorizedException('Invalid or expired access token');
    req.user = data.user;
    const permission = this.reflector.getAllAndOverride<Permission>('permission', [context.getHandler(), context.getClass()]);
    // Missing route declarations fail closed, including newly added handlers.
    if (!permission) throw new ForbiddenException('Route has no permission declaration');
    const cid = req.params.clinicId;
    if (typeof cid !== 'string' || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(cid ?? '')) throw new ForbiddenException('Invalid clinic');
    const result = await req.db.rpc('has_permission', { cid, wanted: permission });
    if (result.error || result.data !== true) throw new ForbiddenException('Permission denied');
    return true;
  }
}
