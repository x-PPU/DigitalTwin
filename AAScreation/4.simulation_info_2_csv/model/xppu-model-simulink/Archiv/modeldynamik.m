syms theta_1(t) theta_2(t) phi(t) Z(t) L l t M m g I dot_theta1(t) dot_theta2(t) dot_phi(t) dot_Z(t) ddot_theta1 ddot_theta2 ddot_phi ddot_Z
x=L*cos(phi)+l*cos(phi)*sin(theta_1)*cos(theta_2)-l*sin(phi)*sin(theta_2);
y=L*sin(phi)+l*sin(phi)*sin(theta_1)*cos(theta_2)+l*cos(phi)*sin(theta_2);
z=Z-l*cos(theta_2)*cos(theta_1);

dot_x=diff(x,t);
dot_y=diff(y,t);
dot_z=diff(z,t);

T=1/2*I*dot_phi^2+1/2*M*diff(Z,t)^2+1/2*m*(dot_x^2+dot_y^2+dot_z^2);

V=M*g*Z+m*g*z;

L=T-V;
%F_vacuum=mg/(cos(theta_1)*cos(theta_2))

A=subs(L,[diff(theta_1,t),diff(theta_2,t),diff(phi,t),diff(Z,t)],[dot_theta1,dot_theta2,dot_phi,dot_Z]);

%Langrange-equation in theta_1
B_1=diff(functionalDerivative(A,dot_theta1),t)-functionalDerivative(A,theta_1);
L_1=simplify(subs(B_1,[diff(theta_1,t),diff(theta_2,t),diff(dot_theta1(t), t)],[dot_theta1,dot_theta2,ddot_theta1]));

%Langrange-equation in theta_2
B_2=diff(functionalDerivative(A,dot_theta2),t)-functionalDerivative(A,theta_2);
L_2=simplify(subs(B_2,[diff(theta_1,t),diff(theta_2,t),diff(dot_theta2(t), t)],[dot_theta1,dot_theta2,ddot_theta2]));

%Langrange-equation in phi =M-Mf
B_3=diff(functionalDerivative(A,dot_phi),t)-functionalDerivative(A,phi);
L_3=simplify(subs(B_3,[diff(theta_1,t),diff(theta_2,t),diff(dot_phi,t)],[dot_theta1,dot_theta2,ddot_phi]));

%Langrange-equation in Z =F-Ff
B_4=diff(functionalDerivative(A,dot_Z),t)-functionalDerivative(A,Z);
L_4=simplify(subs(B_4,[diff(theta_1,t),diff(theta_2,t),diff(dot_Z,t)],[dot_theta1,dot_theta2,ddot_Z]));