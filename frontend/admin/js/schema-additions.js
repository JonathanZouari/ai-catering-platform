// Schema foundation only: no AI executor or scheduling enforcement is enabled here.
const foundationId = { name: 'id', label: 'מספר רשומה', type: 'id', pk: true };
const foundationCreated = { name: 'created_at', label: 'נוצר בתאריך', type: 'timestamp', generated: true };
const ref = (name, label, table, nullable = false) => ({ name, label, type: 'fk', fk: { table, column: 'id' }, nullable });
const server = { hiddenFromData: true, readOnlyReason: 'מבנה בלבד; המידע נגיש לשרת בלבד.' };

export const FOUNDATION_GROUPS = [
  { id: 'availability', label: 'זמינות' },
  { id: 'assistant', label: 'שיחות והצעות שינוי' },
];
export const FOUNDATION_TABLES = [
  {
    name: 'time_slots', label: 'חלונות זמן', group: 'availability',
    description: 'תשתית לזמינות. אכיפת הזמנים בטופס ההזמנה טרם חוברה.',
    readOnlyReason: 'תצוגת תשתית בלבד בשלב זה.',
    columns: [foundationId,
      { name: 'fulfillment_type', label: 'אופן קבלה', type: 'enum', options: { pickup: 'איסוף', delivery: 'משלוח' } },
      { name: 'weekday', label: 'יום בשבוע', type: 'int', nullable: true },
      { name: 'start_time', label: 'שעת התחלה', type: 'text' },
      { name: 'end_time', label: 'שעת סיום', type: 'text' },
      { name: 'capacity', label: 'קיבולת', type: 'int', nullable: true },
      { name: 'is_active', label: 'פעיל', type: 'bool' }, foundationCreated],
  },
  {
    name: 'blocked_dates', label: 'תאריכים חסומים', group: 'availability',
    description: 'תשתית לחסימת ימים. אכיפת החסימה בטופס טרם חוברה.',
    readOnlyReason: 'תצוגת תשתית בלבד בשלב זה.',
    columns: [foundationId, { name: 'date', label: 'תאריך', type: 'date', unique: true },
      { name: 'reason', label: 'סיבה', type: 'text', nullable: true }, foundationCreated],
  },
  {
    name: 'ai_conversations', label: 'שיחות להזמנה', group: 'assistant', ...server,
    description: 'תשתית לשיחה המשויכת להזמנה; אין עדיין חיבור למנוע שיחה.',
    columns: [foundationId, ref('order_id', 'הזמנה', 'orders'), foundationCreated],
  },
  {
    name: 'ai_messages', label: 'הודעות בשיחה', group: 'assistant', ...server,
    description: 'תוכן ההודעות נשמר בצד השרת בלבד.',
    columns: [foundationId, ref('conversation_id', 'שיחה', 'ai_conversations'),
      { name: 'role', label: 'כותב ההודעה', type: 'enum', options: { user: 'לקוח', assistant: 'עוזר', tool: 'כלי' } },
      { name: 'content', label: 'תוכן', type: 'jsonb' }, foundationCreated],
  },
  {
    name: 'ai_change_proposals', label: 'הצעות שינוי להזמנה', group: 'assistant', ...server,
    description: 'תיעוד הצעה ומחיריה. עצם הוספת הרשומה אינו משנה הזמנה.',
    columns: [foundationId, ref('order_id', 'הזמנה', 'orders'), ref('conversation_id', 'שיחה', 'ai_conversations', true),
      { name: 'base_order_version', label: 'גרסת הזמנה מקורית', type: 'int' },
      { name: 'changes', label: 'שינויים מוצעים', type: 'jsonb' },
      { name: 'price_before_minor', label: 'מחיר לפני שינוי', type: 'money' },
      { name: 'price_after_minor', label: 'מחיר אחרי שינוי', type: 'money' },
      { name: 'status', label: 'מצב', type: 'enum', options: { pending: 'ממתין', approved: 'בוצע באישור', rejected: 'נדחה', expired: 'פג תוקף', failed: 'נכשל' } },
      foundationCreated, { name: 'decided_at', label: 'מועד החלטה', type: 'timestamp', nullable: true },
      { name: 'executed_at', label: 'מועד ביצוע', type: 'timestamp', nullable: true }],
  },
];
export const FOUNDATION_RELATIONS = [
  { from: 'orders', columns: ['time_slot_id'], to: 'time_slots', toColumns: ['id'], optional: true },
  { from: 'ai_conversations', columns: ['order_id'], to: 'orders', toColumns: ['id'] },
  { from: 'ai_messages', columns: ['conversation_id'], to: 'ai_conversations', toColumns: ['id'] },
  { from: 'ai_change_proposals', columns: ['order_id'], to: 'orders', toColumns: ['id'] },
  { from: 'ai_change_proposals', columns: ['conversation_id', 'order_id'], to: 'ai_conversations', toColumns: ['id', 'order_id'], optional: true },
];
