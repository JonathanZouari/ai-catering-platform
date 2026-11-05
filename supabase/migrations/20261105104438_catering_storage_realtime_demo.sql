-- Private dish media, authorized realtime and unmistakably synthetic course fixtures.
-- The migration runner owns the transaction. Apply only to the new catering project.
alter table public.dishes add column image_path text
  check (image_path is null or (
    split_part(image_path,'/',1)='dishes' and split_part(image_path,'/',2)=id
    and image_path ~ '^dishes/[^/]+/[a-zA-Z0-9-]+\.(jpg|jpeg|png|webp)$'
  ));

insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
values('dish-images','dish-images',false,5242880,array['image/jpeg','image/png','image/webp']);

create policy catering_images_read on storage.objects for select to authenticated
using (bucket_id='dish-images' and
  (select auth.jwt()->'app_metadata'->>'role') in ('catering_owner','catering_manager'));
create policy catering_images_insert on storage.objects for insert to authenticated
with check (bucket_id='dish-images'
  and (select auth.jwt()->'app_metadata'->>'role') in ('catering_owner','catering_manager')
  and split_part(name,'/',1)='dishes'
  and exists(select 1 from public.dishes d where d.id=split_part(name,'/',2)));
create policy catering_images_update on storage.objects for update to authenticated
using (bucket_id='dish-images' and
  (select auth.jwt()->'app_metadata'->>'role') in ('catering_owner','catering_manager'))
with check (bucket_id='dish-images'
  and (select auth.jwt()->'app_metadata'->>'role') in ('catering_owner','catering_manager')
  and split_part(name,'/',1)='dishes'
  and exists(select 1 from public.dishes d where d.id=split_part(name,'/',2)));
create policy catering_images_delete on storage.objects for delete to authenticated
using (bucket_id='dish-images' and
  (select auth.jwt()->'app_metadata'->>'role') in ('catering_owner','catering_manager'));

-- Private submission hashes/payloads are deliberately not broadcast.
alter publication supabase_realtime add table
  public.customers, public.employees, public.addresses, public.events, public.orders,
  public.deliveries, public.payments, public.equipment_items, public.equipment_movements,
  public.ingredients, public.ingredient_batches, public.ingredient_movements,
  public.dishes, public.delivery_zones, public.order_items;

do $seed$
declare
  cid bigint; aid bigint; eid bigint; oid bigint; driver bigint;
  equipment bigint; ingredient bigint; batch bigint;
  index integer; stamp timestamptz; chosen_status text;
begin
  insert into public.employees(full_name,role,phone)
    values('בעלים להדגמה','owner','0500000000'),
          ('מנהל להדגמה','manager','0500000001'),
          ('טבח להדגמה','chef','0500000002');
  insert into public.employees(full_name,role,phone)
    values('נהג להדגמה','driver','0500000003') returning id into driver;
  insert into public.equipment_items(name,category,replacement_cost_minor)
    values('שולחן הדגמה','table',25000) returning id into equipment;
  insert into public.equipment_movements(equipment_item_id,movement_type,quantity,notes)
    values(equipment,'purchase',20,'נתונים סינתטיים לתרגול בלבד');
  insert into public.equipment_items(name,category,replacement_cost_minor)
    values('מגש הגשה להדגמה','serving_utensil',8000);
  insert into public.ingredients(name,base_unit,reorder_level)
    values('אורז להדגמה','g',5000) returning id into ingredient;
  insert into public.ingredient_batches(ingredient_id,lot_code,supplier_name,received_on,expires_on,total_cost_minor)
    values(ingredient,'DEMO-RICE-001','ספק הדגמה',current_date,current_date+180,12000)
    returning id into batch;
  insert into public.ingredient_movements(batch_id,movement_type,quantity,notes)
    values(batch,'receipt',30000,'נתונים סינתטיים לתרגול בלבד');
  insert into public.ingredients(name,base_unit,reorder_level)
    values('שמן להדגמה','ml',2000),('ביצים להדגמה','unit',30);
  for index in 1..3 loop
    chosen_status := case when index=1 then 'pending_approval' else 'approved' end;
    stamp := ((current_date+20+index)::text || ' 12:00')::timestamp at time zone 'Asia/Jerusalem';
    insert into public.customers(full_name,email,phone)
      values('לקוח הדגמה '||index,'demo'||index||'@catering.example','050000001'||index)
      returning id into cid;
    insert into public.addresses(customer_id,label,street,house_number,city,access_notes)
      values(cid,'כתובת סינתטית','רחוב הדגמה',index::text,'תל אביב-יפו','אין לבצע משלוח אמיתי')
      returning id into aid;
    insert into public.events(customer_id,event_type,event_date,adults,children,vegetarian_guests,dietary_notes)
      values(cid,'אירוע הדגמה',current_date+20+index,20,5,3,'נתונים סינתטיים בלבד') returning id into eid;
    insert into public.orders(customer_id,event_id,status,fulfillment_type,requested_at,
      delivery_address_id,subtotal_minor,delivery_fee_minor,total_minor,submitted_at,decided_at,decision_note)
      values(cid,eid,chosen_status,'delivery',stamp,aid,25500,6000,31500,now(),
      case when chosen_status='approved' then now() else null end,'בקשת הדגמה בלבד') returning id into oid;
    insert into public.order_items(order_id,dish_id,name,unit,quantity_milli,unit_price_minor,line_total_minor)
      values(oid,'d1','חומוס ביתי','tray',3000,8500,25500);
    if chosen_status='approved' then
      insert into public.deliveries(order_id,address_id,driver_employee_id,window_start,window_end,notes)
        values(oid,aid,driver,stamp,stamp+interval '2 hours','משלוח סינתטי — אין לבצע');
      insert into public.payments(kind,order_id,currency,amount_minor,method,document_number,occurred_at)
        values('receipt',oid,'ILS',31500,'other','DEMO-RECEIPT-'||index,now());
      insert into public.equipment_movements(equipment_item_id,movement_type,quantity,order_id,notes)
        values(equipment,'dispatch',4,oid,'תנועת הדגמה');
      insert into public.ingredient_movements(batch_id,movement_type,quantity,order_id,notes)
        values(batch,'consumption',2000,oid,'צריכת הדגמה');
    end if;
  end loop;
end; $seed$;
