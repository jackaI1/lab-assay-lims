import 'reflect-metadata';
import { BadRequestException, Body, Controller, Get, HttpCode, HttpException, Module, NotFoundException, Param, ParseUUIDPipe, Patch, Post, Req, ValidationPipe } from '@nestjs/common';
import { APP_GUARD, NestFactory } from '@nestjs/core';
import { IsBoolean, IsIn, IsString, IsUUID, Length } from 'class-validator';
import { AccessGuard, ClinicRequest, permissions, Public, RequirePermission, roles } from './access';

class NoteInput {
  @IsUUID() patient_id!: string;
  @IsString() @Length(1, 4000) body!: string;
}
class NoteUpdate { @IsString() @Length(1, 4000) body!: string }
class AppointmentUpdate { @IsIn(['scheduled', 'arrived', 'cancelled']) status!: string }
class PermissionUpdate {
  @IsIn(roles) role!: string;
  @IsIn(permissions) permission!: string;
  @IsBoolean() enabled!: boolean;
}
class MemberUpdate { @IsIn(roles) role!: string }
function checked<T>({ data, error }: { data: T; error: { code?: string } | null }): T {
  if (error) {
    if (error.code === '42501') throw new HttpException('Permission denied', 403);
    if (error.code === 'P0002') throw new NotFoundException();
    throw new BadRequestException('Database rejected the operation');
  }
  return data;
}
@Controller()
class HealthController { @Get('health') @Public() health() { return { status: 'ok' }; } }
@Controller('clinics/:clinicId')
class ClinicController {
  @Get('patients') @RequirePermission('patients.read')
  async patients(@Req() req: ClinicRequest, @Param('clinicId') cid: string) {
    return checked(await req.db.from('patients').select('*').eq('clinic_id', cid).order('display_name'));
  }
  @Get('patients/:id') @RequirePermission('patients.read')
  async patient(@Req() req: ClinicRequest, @Param('clinicId') cid: string, @Param('id', ParseUUIDPipe) id: string) {
    const data = checked(await req.db.from('patients').select('*').eq('clinic_id', cid).eq('id', id).maybeSingle());
    if (!data) throw new NotFoundException();
    return data;
  }
  @Get('notes') @RequirePermission('notes.read')
  async notes(@Req() req: ClinicRequest, @Param('clinicId') cid: string) {
    return checked(await req.db.from('notes').select('*').eq('clinic_id', cid).order('created_at'));
  }
  @Post('notes') @RequirePermission('notes.write')
  async addNote(@Req() req: ClinicRequest, @Param('clinicId') cid: string, @Body() input: NoteInput) {
    return checked(await req.db.from('notes').insert({ ...input, clinic_id: cid, author_id: req.user.id }).select().single());
  }
  @Patch('notes/:id') @RequirePermission('notes.write')
  async updateNote(@Req() req: ClinicRequest, @Param('clinicId') cid: string, @Param('id', ParseUUIDPipe) id: string, @Body() input: NoteUpdate) {
    const data = checked(await req.db.from('notes').update(input).eq('clinic_id', cid).eq('id', id).select().maybeSingle());
    if (!data) throw new NotFoundException();
    return data;
  }
  @Get('appointments') @RequirePermission('appointments.read')
  async appointments(@Req() req: ClinicRequest, @Param('clinicId') cid: string) {
    return checked(await req.db.from('appointments').select('*').eq('clinic_id', cid).order('starts_at'));
  }
  @Patch('appointments/:id') @RequirePermission('appointments.write')
  async appointment(@Req() req: ClinicRequest, @Param('clinicId') cid: string, @Param('id', ParseUUIDPipe) id: string, @Body() input: AppointmentUpdate) {
    const data = checked(await req.db.from('appointments').update(input).eq('clinic_id', cid).eq('id', id).select().maybeSingle());
    if (!data) throw new NotFoundException();
    return data;
  }
  @Post('permissions') @HttpCode(204) @RequirePermission('roles.manage')
  async permission(@Req() req: ClinicRequest, @Param('clinicId') cid: string, @Body() input: PermissionUpdate) {
    checked(await req.db.rpc('set_role_permission', { cid, target_role: input.role, wanted: input.permission, enabled: input.enabled }));
  }
  @Patch('members/:id') @HttpCode(204) @RequirePermission('roles.manage')
  async member(@Req() req: ClinicRequest, @Param('clinicId') cid: string, @Param('id', ParseUUIDPipe) id: string, @Body() input: MemberUpdate) {
    checked(await req.db.rpc('set_member_role', { cid, member_id: id, new_role: input.role }));
  }
  @Get('audit') @RequirePermission('audit.read')
  async audit(@Req() req: ClinicRequest, @Param('clinicId') cid: string) {
    return checked(await req.db.from('permission_audit').select('*').eq('clinic_id', cid).order('id'));
  }
}
@Module({ controllers: [HealthController, ClinicController], providers: [{ provide: APP_GUARD, useClass: AccessGuard }] })
export class AppModule {}
export async function createApp() {
  const app = await NestFactory.create(AppModule, { logger: false });
  app.useGlobalPipes(new ValidationPipe({ whitelist: true, forbidNonWhitelisted: true, transform: true }));
  await app.init();
  return app;
}
