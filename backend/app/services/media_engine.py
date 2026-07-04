from app.schemas.prajatantra import HeadlineRequest


class MediaEngine:
    def generate(self, payload: HeadlineRequest) -> list[str]:
        headlines: list[str] = []
        gap = max(0, payload.public_budget - payload.actual_value)
        gap_ratio = gap / payload.public_budget if payload.public_budget else 0

        if gap_ratio >= 0.25 and payload.mayor_wealth_delta > gap * 0.5:
            headlines.append(
                f"{payload.mayor_username}'s sudden wealth sparks graft rumors as {payload.department_name} delivery falls short."
            )
        if payload.health_delta <= -8:
            headlines.append(
                f"Hospital indicators slide despite fresh {payload.department_name} allocations."
            )
        if payload.gdp_delta >= 5 and gap_ratio >= 0.2:
            headlines.append(
                "GDP bump masks widening procurement gap, opposition auditors say."
            )
        if not headlines:
            headlines.append("City desk reports stable public services as the 7-day cycle enters campaign mode.")

        return headlines


media_engine = MediaEngine()

