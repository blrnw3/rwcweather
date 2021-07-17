import math
import os

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Numeric, DateTime


Base = declarative_base()

C = (
    -8.78469475556,
    1.61139411,
    2.33854883889,
    -0.14611605,
    -0.012308094,
    -0.0164248277778,
    0.002211732,
    0.00072546,
    -0.000003582
)


def hi(t, h):
    r = h
    t2 = pow(t, 2)
    r2 = pow(r, 2)

    gamma = (17.271 * t) / (237.7 + t) + math.log(h/ 100)
    d = (237.7 * gamma) / (17.271 - gamma)

    hidx = (C[0] + C[1] * t + C[2] * r + C[3] * t * r +
            C[4] * t2 + C[5] * r2 + C[6] * t2 * r +
            C[7] * t * r2 + C[8] * t2 * r2)

    humidex = t + 0.5555 * (6.11 * pow(math.e, 5417.753 * (0.003660858 - 1 / (d + 273.15))) - 10)

    print((t, h, round(d, 1)), round(hidx, 1), round(humidex, 1))


if __name__ == "__main__":
    hi(23, 50)
    hi(24, 50)
    hi(25, 50)
    hi(26, 50)
    hi(27, 50)
    print()
    hi(27, 40)
    hi(31, 40)
    hi(35, 40)
    hi(40, 40)
    print()
    hi(27, 50)
    hi(31, 50)
    hi(35, 50)
    hi(40, 50)
    print()
    hi(27, 60)
    hi(31, 60)
    hi(35, 60)
    hi(40, 60)
