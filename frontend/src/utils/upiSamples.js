// Sample notifications for the simulator. They imitate the *style* of real UPI app
// notifications; the backend parser decides whether each is a real payment.
export const SAMPLE_NOTIFICATIONS = [
  { label: 'PhonePe · Cafe ₹120', source_app: 'phonepe', title: 'Payment Successful', text: '₹120 paid to Campus Cafe. UPI Ref No. {ref}' },
  { label: 'GPay · Friend ₹500', source_app: 'gpay', title: 'Google Pay', text: 'You paid ₹500.00 to Rahul Sharma using UPI. UPI transaction ID {ref}' },
  { label: 'Paytm · Swiggy ₹249', source_app: 'paytm', title: 'Paytm', text: 'Rs.249 paid to Swiggy successfully. Ref: {ref}' },
  { label: 'PhonePe · Uber ₹186', source_app: 'phonepe', title: 'Payment Successful', text: '₹186 paid to Uber India. UPI Ref No. {ref}' },
  { label: 'GPay · Tea ₹20 (no ref)', source_app: 'gpay', title: 'Google Pay', text: 'You paid ₹20 to Chai Point' },
  { label: 'Received ₹1,000 (ignored)', source_app: 'phonepe', title: 'Money received', text: 'Received ₹1,000 from Mom' },
  { label: 'Request ₹300 (ignored)', source_app: 'gpay', title: 'Payment request', text: 'Riya requested ₹300 from you' },
  { label: 'Failed ₹80 (ignored)', source_app: 'paytm', title: 'Paytm', text: 'Payment of ₹80 to Auto failed' },
]

export const randomRef = () => String(Math.floor(1e11 + Math.random() * 9e11))

export const SOURCE_APPS = [
  { value: 'phonepe', label: 'PhonePe', cls: 'bg-violet-50 text-violet-700 ring-violet-200' },
  { value: 'gpay', label: 'Google Pay', cls: 'bg-sky-50 text-sky-700 ring-sky-200' },
  { value: 'paytm', label: 'Paytm', cls: 'bg-cyan-50 text-cyan-800 ring-cyan-200' },
  { value: 'bhim', label: 'BHIM', cls: 'bg-orange-50 text-orange-700 ring-orange-200' },
  { value: 'other', label: 'UPI', cls: 'bg-slate-100 text-slate-700 ring-slate-200' },
]
export const sourceApp = (v) => SOURCE_APPS.find((s) => s.value === v) || SOURCE_APPS[SOURCE_APPS.length - 1]
