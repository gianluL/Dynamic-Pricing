from flask import Flask, jsonify
from flask import request
import joblib

app = Flask(__name__)


modelSVR, ref_cols, target = joblib.load("rideSVRmodel.pkl") # importing the model

# predict cost factor only

# localhost:8000/cf/400/500/4/0/1/3

@app.route('/cf/<Number_of_Riders>/<Number_of_Drivers>/<Average_Ratings>/<Vehicle_Premium>/<min_costFactor_threshold>/<max_costFactor_threshold>')
def predictCostFactorOnly(Number_of_Riders, Number_of_Drivers, Average_Ratings, Vehicle_Premium, min_costFactor_threshold=0.5, max_costFactor_threshold=10):

    X = [[float(Average_Ratings), int(Vehicle_Premium), (int(Number_of_Riders)/int(Number_of_Drivers))]]

    cost_factor = modelSVR.predict(X)

    if (cost_factor[0] < max(int(min_costFactor_threshold), 0)): # a negative cost-factor is assumed to be unacceptable
        scf = max(int(min_costFactor_threshold), 0)
    elif (cost_factor[0] > int(max_costFactor_threshold)):
        scf = int(max_costFactor_threshold)
    else:
        scf = cost_factor[0]

    dataSCF = {'suggested_surge_multiplier': scf}
    return jsonify(dataSCF)







# predict the entire ride's cost


def predictPlatformCostFactor(Number_of_Riders, Number_of_Drivers, Average_Ratings, Vehicle_Premium, min_costFactor_threshold=0.5, max_costFactor_threshold=10):

    X = [[Average_Ratings, Vehicle_Premium, (Number_of_Riders/Number_of_Drivers)]]

    cost_factor = modelSVR.predict(X)

    if (cost_factor[0] < max(min_costFactor_threshold, 0)): # a negative cost-factor is assumed to be unacceptable
        scf = max(min_costFactor_threshold, 0)
    elif (cost_factor[0] > max_costFactor_threshold):
        scf = max_costFactor_threshold
    else:
        scf = cost_factor[0]

    print("Suggested surge multiplier:", scf)

    return scf

def predictFuelCosts (Expected_ride_km, Cost_1kwh=0, Cost_1lGPL=0, Cost_1kgHydrogen=0, Cost_1lpetrol=0, Cost_1ldiesel=0, Cost_1kgMethane=0, KM_per_1kwh=0, KM_per_1lGPL=0, KM_per_1kgHydrogen=0, KM_per_1lpetrol=0, KM_per_1ldiesel=0, KM_per_1kgMethane=0):
    """
    Takes the expected ride in km and the costs of various fueling sources (energy, GPL, hydrogen, petrol, diesel and methane).
    It also considers the driver's car's mileage for all of the given fuel sources.
    It thus computes the fueling costs for the ride.
    The assumption is that cars using more than one source of fueling spread the usage of the types of fuels equally (e.g. 50% energy and 50% petrol).
    """

    # dividing by the number of provided energy sources. Hence plug-in hybrid electric-gas cars, for example, are assumed to be using 50% of electricity and 50% of gas
    fuel_types = 0
    fuel_count = 0
    if (Cost_1kwh != 0):
        fuel_types += 1
        fuel_count += (Expected_ride_km / KM_per_1kwh) * Cost_1kwh
    if (Cost_1lGPL != 0):
        fuel_types += 1
        fuel_count += (Expected_ride_km / KM_per_1lGPL) * Cost_1lGPL
    if (Cost_1kgHydrogen != 0):
        fuel_types += 1
        fuel_count += (Expected_ride_km / KM_per_1kgHydrogen) * Cost_1kgHydrogen
    if (Cost_1lpetrol != 0):
        fuel_types += 1
        fuel_count += (Expected_ride_km / KM_per_1lpetrol) * Cost_1lpetrol
    if (Cost_1ldiesel != 0):
        fuel_types += 1
        fuel_count += (Expected_ride_km / KM_per_1ldiesel) * Cost_1ldiesel
    if (Cost_1kgMethane != 0):
        fuel_types += 1
        fuel_count += (Expected_ride_km / KM_per_1kgMethane) * Cost_1kgMethane

    fuel_cost = fuel_count / fuel_types
    #print("Fuel count: ", fuel_count)
    print("Fuel types: ", fuel_types)
    print("Fuel cost: €", round(fuel_cost, 2))

    return fuel_cost

def predictSideCosts(Driver_car_price, Expected_Ride_Duration, Driver_yearly_insurance, Driver_yearly_maintenance, Expected_ride_km, dep_car_age=18, dep_car_km=200000, dep_method=0, residual_vehicle_value=0, fixed_costs=0):
    """
    Takes the driver's car original purchase price as new and computes linear depreciation (assuming a lifespan of 18 years), insurance costs (assuming a yearly insurance fee) and maintenance costs (starting from a yearly cost rate).
    The costs are computed and returned considering the expected duration (in minutes) of the ride.
    """
    Driver_car_value = Driver_car_price - residual_vehicle_value    # one may optionally want some residual value to be kept at the end of the vehicle's useful life
    # computing the depreciation of the vehicle, assuming a lifespan of [18] years and adopting a linear time-based depreciation method
    dep_time_mins = dep_car_age * 365.25 * 24 * 60 # ([18] years * 365.25 days (for leap years of 366 days)) times 24 hours times 60 minutes
    dep_cost_min = Expected_Ride_Duration * Driver_car_value / dep_time_mins  # depreciation price of a car within the assigned timeslot  ----   Driver_car_price : dep_time_mins = x : Expected_Ride_Duration --> Expected_Ride_Duration * Driver_car_price / dep_time_mins
    # computing the depreciation of the vehicle in a unit-of-work-based fashion
    dep_cost_km = Expected_ride_km * Driver_car_value / dep_car_km

    if (dep_method == 0): # time-based only
        dep_cost = dep_cost_min
    elif (dep_method == 1): # unit-based only
        dep_cost = dep_cost_km
    elif (dep_method == 2): # 50-50 combination of time-based and unit based
        dep_cost = (dep_cost_min/2) + (dep_cost_km/2)

    # computing insurance costs
    ins_cost = Expected_Ride_Duration * Driver_yearly_insurance / (dep_time_mins/dep_car_age)  # allocating costs of insurance to the ride (per year)

    # computing maintenance costs
    main_cost = Expected_Ride_Duration * Driver_yearly_maintenance / (dep_time_mins/dep_car_age)  # allocating costs of maintenance to the ride (per year)

    side_costs = dep_cost + ins_cost + main_cost + fixed_costs


    print("Depreciation cost (method:", dep_method, "): €", round(dep_cost,7))
    print("Insurance cost: €", round(ins_cost, 7))
    print("Maintenance cost: €", round(main_cost, 7))
    print("Fixed costs: €", round(fixed_costs, 2))

    return side_costs



#http://localhost:8000/rc/3/15000/11/1300/21/1400/12/157/212/3.9/0.29/0/0/1.79/0/0/7.8/0/0/17.3/0/0/40000/18/18/120312/2/2000/1.5/6/1/0.1/False/0.2/0.2/0.22
# there is no (straighforward) way to include/support default values for some parameters...you may solve by using request.body (instead of taking things from the url) and then, if .. == None, allora passi il default value

@app.route('/rc/<tot_ride_passengers>/<Driver_car_price>/<Driver_car_years>/<Driver_yearly_insurance>/<Expected_Ride_Duration>/<Driver_yearly_maintenance>/<Expected_ride_km>/<Number_of_Riders>/<Number_of_Drivers>/<Average_Ratings>/<Cost_1kwh>/<Cost_1lGPL>/<Cost_1kgHydrogen>/<Cost_1lpetrol>/<Cost_1ldiesel>/<Cost_1kgMethane>/<KM_per_1kwh>/<KM_per_1lGPL>/<KM_per_1kgHydrogen>/<KM_per_1lpetrol>/<KM_per_1ldiesel>/<KM_per_1kgMethane>/<premium_car_price>/<Premium_car_years>/<dep_car_age>/<dep_car_km>/<dep_method>/<residual_vehicle_value>/<min_costFactor_threshold>/<max_costFactor_threshold>/<Fixed_fee>/<driver_pct_fee>/<Driver_pays>/<fixed_costs>/<transaction_cost>/<tax_rate>')
def predictSuggestedCost(tot_ride_passengers, Driver_car_price, Driver_car_years, Driver_yearly_insurance, Expected_Ride_Duration, Driver_yearly_maintenance, Expected_ride_km, Number_of_Riders, Number_of_Drivers, Average_Ratings, Cost_1kwh=0, Cost_1lGPL=0, Cost_1kgHydrogen=0, Cost_1lpetrol=0, Cost_1ldiesel=0, Cost_1kgMethane=0, KM_per_1kwh=0, KM_per_1lGPL=0, KM_per_1kgHydrogen=0, KM_per_1lpetrol=0, KM_per_1ldiesel=0, KM_per_1kgMethane=0, premium_car_price=40000, Premium_car_years=18, dep_car_age=18, dep_car_km=200000, dep_method=0, residual_vehicle_value=0, min_costFactor_threshold=0, max_costFactor_threshold=10, Fixed_fee=0, driver_pct_fee=0, Driver_pays=False, fixed_costs=0, transaction_cost=0, tax_rate=0):
    """
    Suggests the driver a cost to charge the rider based on the parameters given. The minimum price always takes into account fueling, depreciation, maintenance and insurance costs.
    The costs are computed and returned in euros (€) considering the given parameters of the ride.

    Explanation of the parameters:
    - tot_ride_passengers: total number of passengers in the vehicle, including the driver;
    - Driver_car_price: price in euros (€) of the car when bought as new;
    - Driver_car_years: the car age computed starting from when it was bought as brand new;
    - Driver_yearly_insurance: the yearly cost in euros (€) the driver must pay for insurance;
    - Expected_Ride_Duration: expected duration of the ride in minutes;
    - Driver_yearly_maintenance: the yearly average cost in euros (€) the driver pays for maintaining the vehicle;
    - Expected_ride_km: expected length of the ride in kilometers;
    - Number_of_Riders: number of available riders willing to share a ride at the time of the booking;
    - Number_of_Drivers: number of available drivers willing to provide a ride at the time of the booking;
    - Average_Ratings: accepts values from 1 to 5 and is the average rating given by the customer/rider to the rides he shared;
    - Cost_1kwh: the current average cost in euros (€) of 1 kWh of energy within the area. It is '0' by default;
    - Cost_1lGPL: the current average cost in euros (€) of 1 litre of liquefied petroleum gas within the area. It is '0' by default;
    - Cost_1kgHydrogen: the current average cost in euros (€) of 1 kilogram of hydrogen within the area. It is '0' by default;
    - Cost_1lpetrol: the current average cost in euros (€) of 1 litre of petrol within the area. It is '0' by default;
    - Cost_1ldiesel: the current average cost in euros (€) of 1 litre of diesel within the area. It is '0' by default;
    - Cost_1kgMethane: the current average cost in euros (€) of 1 kilogram of methane within the area. It is '0' by default;
    - KM_per_1kwh: the number of kilometers the driver's car can travel on 1 kWh of energy. It is '0' by default;
    - KM_per_1lGPL: the number of kilometers the driver's car can travel on 1 litre of LPG. It is '0' by default;
    - KM_per_1kgHydrogen: the number of kilometers the driver's car can travel on 1 kg of hydrogen. It is '0' by default;
    - KM_per_1lpetrol: the number of kilometers the driver's car can travel on 1 litre of petrol. It is '0' by default;
    - KM_per_1ldiesel: the number of kilometers the driver's car can travel on 1 litre of diesel. It is '0' by default;
    - KM_per_1kgMethane: the number of kilometers the driver's car can travel on 1 kg of methane. It is '0' by default;
    - premium_car_price: the purchase price of a brand new premium car in euros (€) at the time of the booking. It is '40000' by default;
    - Premium_car_years: the number of years after which a car, no matter the purchase price, is no longer considered "premium" . It is '18' by default;
    - dep_car_age: the number of years to consider for the vehicle's time-based linear depreciation. It is '18' by default;
    - dep_car_km: the number of kilometers considered for the vehicle's unit-of-work-based linear depreciation. It is '200000' by default;
    - dep_method: it specifies the type of depreciation method to use: '0' means time-based only, '1' means unit-based only, '2' means a 50%-50% combination of time-based and unit-based. It is '0' by default;
    - residual_vehicle_value: it specifies the residual value in euros (€) of the vehicle, which is thus excluded from the computations of depreciation. It is '0' by default;
    - min_costFactor_threshold: it represents the minimum cost factor threshold that the company is willing to charge. It is '0' by default;
    - max_costFactor_threshold: it represents the maximum cost factor threshold that the company is willing to charge. It is '10' by default;
    - Fixed_fee: a fixed fee in euros (€) a platform may want to charge on top of what is being computed. It is '0' by default;
    - driver_pct_fee: a percentage from 0 to 1 of the surge multiplier part of the cost that a platform may want to leave for the driver (e.g. 0.25 -> 25\%). It is '0' by default;
    - Driver_pays: it can be either "True" or "False" and indicates whether the driver should also contribute in paying its share or not. It is "False" by default;
    - fixed_costs: it specifies any additional and optional fixed fees in euros (€), such as parking and tolls fees. It is '0' by default;
    - transaction_cost: it's the cost in euros (€) of validating the transaction (which may include the allocation per ride of infrastructural costs). It is '0' by default;
    - tax_rate: it is related to the taxation rate. It is '0.1' by default (i.e 10% tax on top of the ride price).
    """


    tot_ride_passengers = int(tot_ride_passengers)
    Driver_car_price = float(Driver_car_price)
    Driver_car_years = float(Driver_car_years)
    Driver_yearly_insurance = float(Driver_yearly_insurance)
    Expected_Ride_Duration = float(Expected_Ride_Duration)
    Driver_yearly_maintenance = float(Driver_yearly_maintenance)
    Expected_ride_km = float(Expected_ride_km)
    Number_of_Riders = float(Number_of_Riders)
    Number_of_Drivers = float(Number_of_Drivers)
    Average_Ratings = float(Average_Ratings)
    Cost_1kwh = float(Cost_1kwh)
    Cost_1lGPL = float(Cost_1lGPL)
    Cost_1kgHydrogen = float(Cost_1kgHydrogen)
    Cost_1lpetrol = float(Cost_1lpetrol)
    Cost_1ldiesel = float(Cost_1ldiesel)
    Cost_1kgMethane = float(Cost_1kgMethane)
    KM_per_1kwh = float(KM_per_1kwh)
    KM_per_1lGPL = float(KM_per_1lGPL)
    KM_per_1kgHydrogen = float(KM_per_1kgHydrogen)
    KM_per_1lpetrol = float(KM_per_1lpetrol)
    KM_per_1ldiesel = float(KM_per_1ldiesel)
    KM_per_1kgMethane = float(KM_per_1kgMethane)
    premium_car_price = float(premium_car_price)
    Premium_car_years = float(Premium_car_years)
    dep_car_age = float(dep_car_age)
    dep_car_km = float(dep_car_km)
    dep_method = int(dep_method)
    residual_vehicle_value = float(residual_vehicle_value)
    min_costFactor_threshold = float(min_costFactor_threshold)
    max_costFactor_threshold = float(max_costFactor_threshold)
    Fixed_fee = float(Fixed_fee)
    driver_pct_fee = float(driver_pct_fee)
    Driver_pays = bool(Driver_pays)
    fixed_costs = float(fixed_costs)
    transaction_cost = float(transaction_cost)
    tax_rate = float(tax_rate)

    # define whether the car is premium or not...any car is considered not premium if older than 18 and if less expensive than 40000
    if (Driver_car_price > premium_car_price and Driver_car_years < Premium_car_years):
        veh_state = 1 # premium
    else:
        veh_state = 0 # not premium

    fuel_cost = predictFuelCosts (Expected_ride_km, Cost_1kwh, Cost_1lGPL, Cost_1kgHydrogen, Cost_1lpetrol, Cost_1ldiesel, Cost_1kgMethane, KM_per_1kwh, KM_per_1lGPL, KM_per_1kgHydrogen, KM_per_1lpetrol, KM_per_1ldiesel, KM_per_1kgMethane)
    if ((Average_Ratings >= 1 and Average_Ratings <= 5) and (veh_state == 0 or veh_state == 1) and (dep_method == 0 or dep_method == 1 or dep_method == 2) and (Driver_pays == True or Driver_pays == False)):
        side_costs = predictSideCosts(Driver_car_price, Expected_Ride_Duration, Driver_yearly_insurance, Driver_yearly_maintenance, Expected_ride_km, dep_car_age, dep_car_km, dep_method, residual_vehicle_value, fixed_costs)
        cost_factor = predictPlatformCostFactor(Number_of_Riders, Number_of_Drivers, Average_Ratings, veh_state, min_costFactor_threshold, max_costFactor_threshold) # this ultimately defines the gain that the driver obtains, depending on market conditions

        if (Driver_pays is False and driver_pct_fee > 0):
            scenario = 'Ride Hailing'
            revenue_platform = transaction_cost + Fixed_fee + ((fuel_cost + side_costs) * (cost_factor * (1 - driver_pct_fee))) # driver_pct_fee > 0 (the platform can receive only part of the surplus)
            profit_platform = (revenue_platform - transaction_cost)
            revenue_driver = (fuel_cost + side_costs) * (1 + cost_factor * driver_pct_fee) # the driver here will always be able to recuperate at least break even costs
            profit_driver = (revenue_driver - (fuel_cost + side_costs))
        elif (Driver_pays is True and driver_pct_fee == 0):
            scenario = 'Vehicle Sharing'
            revenue_platform = transaction_cost + Fixed_fee + (((fuel_cost + side_costs) * (1 + cost_factor * (1 - driver_pct_fee)))) # '1' is here, as the platform is sustaining fueling and side costs...it takes all the surplus --- #driver_pct_fee = 0
            profit_platform = (revenue_platform - transaction_cost - fuel_cost - side_costs)
            revenue_driver = (((fuel_cost + side_costs) * (cost_factor * driver_pct_fee))) # = 0....driver_pct_fee = 0 ---> revenue_driver = 0 (because the driver is considered like any other paying passenger)
            profit_driver = revenue_driver # = 0....the driver does not bear the costs of fueling and additional side costs here, thus profit_driver = 0 as well
        else: # the driver can or cannot contribute, depending on the other passengers' choice. Moreover, he may or may not make any profit from the platform (same formulas as for ride-hailing)
            scenario = 'Ride Sharing'
            revenue_platform = transaction_cost + Fixed_fee + ((fuel_cost + side_costs) * (cost_factor * (1 - driver_pct_fee))) # driver_pct_fee > 0 (the platform can receive only part of the surplus)
            profit_platform = (revenue_platform - transaction_cost)
            revenue_driver = (fuel_cost + side_costs) * (1 + cost_factor * driver_pct_fee) # the driver here will always be able to recuperate at least break even costs
            profit_driver = (revenue_driver - (fuel_cost + side_costs))

        due_tax = (transaction_cost + Fixed_fee + ((fuel_cost + side_costs) * (1 + cost_factor))) * tax_rate
        suggested_cost_ride_beforeTax = transaction_cost + Fixed_fee + ((fuel_cost + side_costs) * (1 + cost_factor))
        suggested_cost_ride = (transaction_cost + Fixed_fee + ((fuel_cost + side_costs) * (1 + cost_factor))) * (1 + tax_rate)


        #print("Scenario -", scenario)
        #print("Final surge multiplier (+1):", 1 + cost_factor) # the multiplier is on top of the break-even price
        #print("Break-even price: €", round((fuel_cost + side_costs), 2))
        
        #print("Optional platform's fixed fee: €", round(Fixed_fee, 2))
        #print("Driver's fee:", driver_pct_fee*100, '%')
        #print("Transaction cost: €", round(transaction_cost, 2))
        
        #print("Platform revenue on ride: €", round(revenue_platform, 2), "--- Platform profit on ride: €", round(profit_platform, 2))
        #print("Driver's revenue on ride: €", round(revenue_driver,2), "--- Driver's profit on ride: €", round(profit_driver, 2))
        #print("Suggested cost of ride without tax: €", round(suggested_cost_ride_beforeTax, 2), "--- which equals driver's plus platform's revenue: €", round(revenue_driver, 4) + round(revenue_platform, 4))
        #print("Due tax: €", round(due_tax, 2), "--- Given tax rate of:", tax_rate)
        #print("\nFinal suggested cost of ride (including tax): €", round(suggested_cost_ride, 2))

        if (Driver_pays is False):
            #print("Each passenger should pay: €", round(suggested_cost_ride/(tot_ride_passengers-1), 2), "(driver doesn't contribute).")
            individual_fee = suggested_cost_ride/(tot_ride_passengers-1)
        else:
            #print("Each passenger should pay: €", round(suggested_cost_ride/tot_ride_passengers, 2), "(driver included).")
            individual_fee = suggested_cost_ride/tot_ride_passengers

        #return suggested_cost_ride
        data = {
            'scenario': scenario,
            'surge_multiplier': 1 + cost_factor,
            'break-even_price_EUR': round((fuel_cost + side_costs),2),
            'platform_revenue_on_ride_EUR': round(revenue_platform,2),
            'platform_profit_on_ride_EUR': round(profit_platform,2),
            'driver_revenue_on_ride_EUR': round(revenue_driver,2),
            'driver_profit_on_ride_EUR': round(profit_driver,2),
            'suggested_overall_ride_cost_before_tax_EUR': round(suggested_cost_ride_beforeTax,2),
            'due_tax_EUR': round(due_tax,2),
            'suggested_overall_ride_cost_EUR': round(suggested_cost_ride,2),
            'individual_fee_EUR': round(individual_fee,2)
        }
        return jsonify(data)
    
    else:
        
        data = {'error': 'Could not suggest a price. Please check the parameter values given and try again!'}
        return jsonify(data)









if __name__ == "__main__": # == or =  // in java, this would be the main Method. must be at the very end, otherwise, it won't work
    app.run(host="0.0.0.0", port=8000, threaded=True, debug=True)

# first you run on built-in terminal:
# python3 /Users/gianlucalorusso/...../library.py      OR
# python3 ./server.py

# then you type in browser:
# http://localhost:8000/___