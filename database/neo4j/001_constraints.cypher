CREATE CONSTRAINT treasury_city_id IF NOT EXISTS
FOR (t:Treasury) REQUIRE t.city_id IS UNIQUE;

CREATE CONSTRAINT project_id IF NOT EXISTS
FOR (p:Project) REQUIRE p.id IS UNIQUE;

CREATE CONSTRAINT account_number IF NOT EXISTS
FOR (a:Account) REQUIRE a.acc_num IS UNIQUE;

CREATE CONSTRAINT player_username IF NOT EXISTS
FOR (p:Player) REQUIRE p.username IS UNIQUE;

CREATE INDEX vendor_shell IF NOT EXISTS
FOR (v:Vendor) ON (v.is_shell);

CREATE INDEX department_portfolio IF NOT EXISTS
FOR (d:Department) ON (d.portfolio_type);

