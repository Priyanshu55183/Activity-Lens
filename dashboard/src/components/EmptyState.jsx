export default function EmptyState() {
  return (
    <div className="empty-state">
      <div className="empty-icon">&#x1F4CA;</div>
      <h3>No Data for This Day</h3>
      <p>
        No activity was recorded. Run <code>python src/seed_data.py</code> to
        generate demo data, or start the capture service with{' '}
        <code>python src/main.py</code>.
      </p>
    </div>
  )
}
